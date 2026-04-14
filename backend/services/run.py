"""
Microservices Entry Point
=========================
Can run as:
1. Single monolithic app (default): python run.py
2. Separate services:
   - API Gateway: python run.py --service api
   - Scraper Worker: python run.py --service scraper
   - Scheduler: python run.py --service scheduler
"""

import sys
import os
import argparse
import threading

# Add backend directory to path for all imports
_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)


def run_api():
    from services.api.main import app
    import uvicorn

    p = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=p)


def run_scraper():
    from services.scraper.main import app
    import uvicorn

    p = int(os.environ.get("SCRAPER_PORT", 8001))
    uvicorn.run(app, host="0.0.0.0", port=p)


def run_scheduler():
    from services.scheduler.service import app
    import uvicorn

    p = int(os.environ.get("SCHEDULER_PORT", 8002))
    uvicorn.run(app, host="0.0.0.0", port=p)


def run_all():
    """Run all services in a single process with threading (simpler deployment)."""
    # Ensure backend directory is in path
    _backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _backend_dir not in sys.path:
        sys.path.insert(0, _backend_dir)

    import uvicorn
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
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
    from services.scraper.service import run_pipeline_sync, DiceScraper
    import httpx
    import time as time_module
    from datetime import datetime
    import re

    app = FastAPI(title="Dice Scraper Pro (All-in-One)")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    state_lock = threading.Lock()
    # Initialize to today so the scheduler won't fire immediately if the app
    # starts after the scheduled time (e.g. restarting at 15:44 when schedule is 08:30).
    scheduler_state = {"last_scheduled_run_date": datetime.now().strftime("%Y-%m-%d")}

    def check_auth(x_api_key):
        if API_KEY and x_api_key != API_KEY:
            raise HTTPException(
                status_code=401, detail="Invalid or missing X-API-Key header"
            )

    from fastapi import HTTPException, Header


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
            active_jobs = sm.get_records_paginated(
                "active-scraped-data", page, half_limit
            )
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
            return {"jobs": [], "page": page, "limit": limit}

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
                "total_jobs": len(active_jobs) + len(inactive_jobs),
                "total_active": len(active_jobs),
                "total_inactive": len(inactive_jobs),
                "scheduler_next_run": scraper_config.get("schedule_time", "Unknown")
                if scraper_config.get("schedule_enabled")
                else "Disabled",
            }
        except Exception as e:
            logger.error(f"Failed to fetch stats: {e}")
            return {"error": "Failed to sync statistics."}

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
                except:
                    raise HTTPException(
                        status_code=400, detail=f"{key} must be a positive integer"
                    )
        logger.info(f"Settings updated: {updated}")
        return {"status": "ok", "updated": updated, "config": scraper_config}

    @app.post("/trigger")
    def trigger_scrape(x_api_key: str = Header(None)):
        check_auth(x_api_key)
        with state_lock:
            if app_state.status in ("running", "starting"):
                return {"message": "Scraper already running"}
            app_state.update(status="starting")
        threading.Thread(
            target=lambda: run_pipeline_sync(dict(scraper_config)), daemon=True
        ).start()
        return {"message": "Scraper started"}

    @app.post("/stop")
    def stop_scrape(x_api_key: str = Header(None)):
        check_auth(x_api_key)
        with state_lock:
            if app_state.status in ("running", "starting"):
                app_state.update(stop_requested=True)
                return {"message": "Stop requested"}
        return {"message": "Scraper is not running"}

    @app.post("/clear-data")
    def clear_data(x_api_key: str = Header(None)):
        check_auth(x_api_key)
        try:
            sm = SheetManager(SERVICE_ACCOUNT_FILE, SPREADSHEET_ID)
            sm.clear_all_data("active-scraped-data")
            sm.clear_all_data("inactive-scraped-data")
            logger.info("Cleared all scraped data sheets")
            return {"status": "ok", "message": "All scraped data cleared"}
        except Exception as e:
            logger.error(f"Failed to clear data: {e}")
            return {"status": "error", "message": str(e)}

    def scheduler_loop():
        logger.info("Starting integrated scheduler...")
        while True:
            try:
                now = datetime.now()
                today = now.strftime("%Y-%m-%d")
                target_time = scraper_config.get("schedule_time", "08:30")
                enabled = scraper_config.get("schedule_enabled", True)

                if enabled:
                    target_dt = datetime.strptime(target_time, "%H:%M")
                    target_dt = target_dt.replace(
                        year=now.year, month=now.month, day=now.day
                    )

                    if (
                        scheduler_state["last_scheduled_run_date"] != today
                        and now >= target_dt
                    ):
                        with state_lock:
                            curr_status = app_state.status
                        if curr_status == "idle":
                            logger.info(
                                f"SCHEDULER: Triggering daily run at {target_time}"
                            )
                            scheduler_state["last_scheduled_run_date"] = today
                            threading.Thread(
                                target=lambda: run_pipeline_sync(dict(scraper_config)),
                                daemon=True,
                            ).start()
                        else:
                            logger.info(
                                f"SCHEDULER: Waiting - scraper busy (status={curr_status})"
                            )
            except Exception as e:
                logger.error(f"Scheduler error: {e}")
            time_module.sleep(10)

    threading.Thread(target=scheduler_loop, daemon=True).start()

    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse

    # Serve Static Files (Frontend)
    # The 'dist' folder is copied to /app/frontend/dist in the Dockerfile
    # _backend_dir is /app
    dist_path = os.path.join(_backend_dir, "frontend", "dist")
    
    if os.path.exists(dist_path):
        logger.info(f"Serving frontend from: {dist_path}")
        # Mount the assets folder specifically
        assets_path = os.path.join(dist_path, "assets")
        if os.path.exists(assets_path):
            app.mount("/assets", StaticFiles(directory=assets_path), name="assets")

        # Catch-all route to serve index.html for React SPA routing
        @app.get("/{full_path:path}")
        async def serve_frontend(full_path: str):
            index_file = os.path.join(dist_path, "index.html")
            return FileResponse(index_file)
    else:
        logger.warning(f"Frontend build not found at {dist_path}. UI will not be served.")

    p = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=p)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Dice Scraper Microservices")
    parser.add_argument(
        "--service",
        choices=["api", "scraper", "scheduler", "all"],
        default="all",
        help="Service to run",
    )
    args = parser.parse_args()

    if args.service == "api":
        print("Starting API Gateway...")
        run_api()
    elif args.service == "scraper":
        print("Starting Scraper Worker...")
        run_scraper()
    elif args.service == "scheduler":
        print("Starting Scheduler Service...")
        run_scheduler()
    else:
        print("Starting all-in-one mode...")
        run_all()
