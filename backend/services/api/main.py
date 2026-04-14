import sys
import os

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

import time
import threading
from datetime import datetime
from fastapi import FastAPI, BackgroundTasks, HTTPException, Header, Body
from fastapi.middleware.cors import CORSMiddleware
import httpx
import uvicorn

from services.common import (
    logger,
    app_state,
    scraper_config,
    DATE_RANGE_MAP,
    SERVICE_ACCOUNT_FILE,
    SPREADSHEET_ID,
    API_KEY,
)
from services.common.sheets import SheetManager

app = FastAPI(title="Dice Scraper API Gateway")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SCRAPER_SERVICE_URL = os.getenv("SCRAPER_SERVICE_URL", "http://localhost:8001")
state_lock = threading.Lock()


def check_auth(x_api_key: str):
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(
            status_code=401, detail="Invalid or missing X-API-Key header"
        )


@app.get("/")
def health():
    return {"status": "ok", "service": "Dice Scraper API Gateway", "version": "2.0"}


@app.get("/status")
def get_status(x_api_key: str = Header(None)):
    check_auth(x_api_key)
    return app_state.to_dict()


@app.get("/jobs")
def get_jobs(page: int = 1, limit: int = 20, x_api_key: str = Header(None)):
    check_auth(x_api_key)
    try:
        sm = SheetManager(SERVICE_ACCOUNT_FILE, SPREADSHEET_ID)
        half_limit = limit // 2
        active_jobs = sm.get_records_paginated("active-scraped-data", page, half_limit)
        inactive_jobs = sm.get_records_paginated(
            "inactive-scraped-data", page, half_limit
        )

        for j in active_jobs:
            j["type"] = "active"
        for j in inactive_jobs:
            j["type"] = "inactive"

        all_jobs = active_jobs + inactive_jobs
        all_jobs.sort(key=lambda x: x.get("scraped_at", ""), reverse=True)

        return {"jobs": all_jobs, "page": page, "limit": limit}
    except Exception as e:
        logger.error(f"Failed to fetch jobs: {e}")
        return {
            "jobs": [],
            "page": page,
            "limit": limit,
            "error": "External API connection error.",
        }


@app.get("/stats")
def get_stats(x_api_key: str = Header(None)):
    check_auth(x_api_key)
    try:
        sm = SheetManager(SERVICE_ACCOUNT_FILE, SPREADSHEET_ID)
        active_jobs = sm.get_all_records("active-scraped-data")
        inactive_jobs = sm.get_all_records("inactive-scraped-data")

        today_str = datetime.now().strftime("%Y-%m-%d")
        jobs_today = sum(
            1
            for j in active_jobs + inactive_jobs
            if j.get("scraped_at") and j["scraped_at"].startswith(today_str)
        )

        return {
            "jobs_scraped_today": jobs_today,
            "new_jobs": len(active_jobs) + len(inactive_jobs),
            "matched_candidates": 72,
            "tailored_resumes": 33,
            "total_jobs": len(active_jobs) + len(inactive_jobs),
            "total_active": len(active_jobs),
            "total_inactive": len(inactive_jobs),
            "scheduler_next_run": scraper_config.get("schedule_time", "Unknown")
            if scraper_config.get("schedule_enabled")
            else "Disabled",
        }
    except Exception as e:
        logger.error(f"Failed to fetch stats: {e}")
        return {
            "jobs_scraped_today": 0,
            "new_jobs": 0,
            "matched_candidates": 0,
            "tailored_resumes": 0,
            "total_jobs": 0,
            "error": "Failed to sync statistics.",
        }


@app.get("/settings")
def get_settings(x_api_key: str = Header(None)):
    check_auth(x_api_key)
    return scraper_config


@app.post("/settings")
def update_settings(payload: dict, x_api_key: str = Header(None)):
    check_auth(x_api_key)
    allowed = {
        "date_range",
        "max_search_pages",
        "max_workers",
        "request_timeout",
        "scrape_cooldown",
        "schedule_enabled",
        "schedule_time",
    }
    updated = {}
    for key, val in payload.items():
        if key not in allowed:
            continue

        if key == "date_range":
            if val not in DATE_RANGE_MAP:
                raise HTTPException(
                    status_code=400, detail=f"Invalid date_range '{val}'"
                )
            scraper_config["date_range"] = val
            scraper_config["date_range_label"] = DATE_RANGE_MAP[val]
            updated[key] = val
        elif key == "schedule_enabled":
            scraper_config[key] = bool(val)
            updated[key] = bool(val)
        elif key == "schedule_time":
            import re

            if not re.match(r"^\d{2}:\d{2}$", str(val)):
                raise HTTPException(
                    status_code=400, detail="schedule_time must be HH:MM format"
                )
            scraper_config[key] = str(val)
            updated[key] = str(val)
        elif key in (
            "max_search_pages",
            "max_workers",
            "request_timeout",
            "scrape_cooldown",
        ):
            try:
                v = int(val)
                if v < 1:
                    raise ValueError
                scraper_config[key] = v
                updated[key] = v
            except (ValueError, TypeError):
                raise HTTPException(
                    status_code=400, detail=f"{key} must be a positive integer"
                )

    logger.info(f"Settings updated: {updated}")
    return {"status": "ok", "updated": updated, "config": scraper_config}


@app.post("/trigger")
async def trigger_scrape(
    x_api_key: str = Header(None), background_tasks: BackgroundTasks = None
):
    check_auth(x_api_key)

    with state_lock:
        if app_state.status in ("running", "starting"):
            return {"message": "Scraper is already running"}
        app_state.update(status="starting")

    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(
                f"{SCRAPER_SERVICE_URL}/run",
                json={"config": dict(scraper_config)},
                headers={"X-API-Key": API_KEY} if API_KEY else {},
            )
            if response.status_code == 200:
                return {
                    "message": "Scraper started",
                    "task_id": response.json().get("task_id"),
                }
            else:
                app_state.update(status="idle")
                return {"message": "Failed to start scraper", "error": response.text}
    except httpx.ConnectError:
        logger.warning("Scraper service not available, running inline")
        from services.scraper.service import run_pipeline_sync

        threading.Thread(
            target=run_pipeline_sync, args=(dict(scraper_config),), daemon=True
        ).start()
        return {"message": "Scraper started inline"}
    except Exception as e:
        logger.error(f"Failed to trigger scrape: {e}")
        app_state.update(status="idle")
        return {"message": f"Failed to start scraper: {str(e)}"}


@app.post("/stop")
def stop_scrape(x_api_key: str = Header(None)):
    check_auth(x_api_key)
    with state_lock:
        if app_state.status in ("running", "starting"):
            app_state.update(stop_requested=True)
            return {"message": "Stop requested. Pipeline will terminate safely soon."}
    return {"message": "Scraper is not running"}


@app.post("/clear-data")
def clear_data(x_api_key: str = Header(None)):
    check_auth(x_api_key)
    try:
        import json

        sm = SheetManager(SERVICE_ACCOUNT_FILE, SPREADSHEET_ID)
        sheets = ["active-scraped-data", "inactive-scraped-data"]
        cleared = []
        for sheet in sheets:
            sm.clear_all_data(sheet)
            cleared.append(sheet)
        logger.info(f"Cleared sheets: {cleared}")
        return {"status": "ok", "message": f"Cleared: {', '.join(cleared)}"}
    except Exception as e:
        logger.error(f"Failed to clear data: {e}")
        return {"status": "error", "message": str(e)}


if __name__ == "__main__":
    p = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=p)
