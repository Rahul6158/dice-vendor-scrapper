import sys
import os

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

import time
import threading
import asyncio
import httpx
from datetime import datetime
import uvicorn
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware

from services.common import logger, scraper_config, API_KEY

app = FastAPI(title="Dice Scraper Scheduler")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

scheduler_state = {"last_scheduled_run_date": None}
scheduler_lock = threading.Lock()
running = True

API_SERVICE_URL = os.getenv("API_SERVICE_URL", "http://localhost:8000")
SCRAPER_SERVICE_URL = os.getenv("SCRAPER_SERVICE_URL", "http://localhost:8001")


def check_auth(x_api_key: str):
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(
            status_code=401, detail="Invalid or missing X-API-Key header"
        )


def scheduler_worker():
    logger.info("Starting scheduler worker thread...")

    while running:
        try:
            now = datetime.now()
            today = now.strftime("%Y-%m-%d")

            target_time = scraper_config.get("schedule_time", "08:30")
            enabled = scraper_config.get("schedule_enabled", True)

            if not enabled:
                time.sleep(10)
                continue

            target_dt = datetime.strptime(target_time, "%H:%M")
            target_dt = target_dt.replace(year=now.year, month=now.month, day=now.day)

            logger.info(
                f"SCHEDULER: now={now.strftime('%H:%M:%S')}, target={target_time}, last_run={scheduler_state.get('last_scheduled_run_date')}"
            )

            with scheduler_lock:
                if (
                    scheduler_state["last_scheduled_run_date"] != today
                    and now >= target_dt
                ):
                    _trigger_scrape(target_time)

        except Exception as e:
            logger.error(f"Scheduler worker error: {e}")

        time.sleep(10)


def _trigger_scrape(target_time: str):
    try:

        async def _async_trigger():
            headers = {"X-API-Key": API_KEY} if API_KEY else {}

            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(
                        f"{API_SERVICE_URL}/trigger", headers=headers
                    )
                    if response.status_code == 200:
                        result = response.json()
                        if "task_id" in result:
                            logger.info(
                                f"SCHEDULER: Successfully triggered scrape via API gateway"
                            )
                            with scheduler_lock:
                                scheduler_state["last_scheduled_run_date"] = (
                                    datetime.now().strftime("%Y-%m-%d")
                                )
                        elif (
                            "message" in result
                            and "inline" in result.get("message", "").lower()
                        ):
                            logger.info(f"SCHEDULER: Triggered inline execution")
                            with scheduler_lock:
                                scheduler_state["last_scheduled_run_date"] = (
                                    datetime.now().strftime("%Y-%m-%d")
                                )
                    else:
                        logger.warning(
                            f"SCHEDULER: Failed to trigger - {response.status_code}: {response.text}"
                        )
            except httpx.ConnectError:
                logger.warning(
                    "SCHEDULER: API service unavailable, trying scraper service directly"
                )
                try:
                    async with httpx.AsyncClient(timeout=30.0) as client:
                        response = await client.post(
                            f"{SCRAPER_SERVICE_URL}/run",
                            json={"config": dict(scraper_config)},
                            headers=headers,
                        )
                        if response.status_code == 200:
                            logger.info(
                                f"SCHEDULER: Triggered scrape via scraper service"
                            )
                            with scheduler_lock:
                                scheduler_state["last_scheduled_run_date"] = (
                                    datetime.now().strftime("%Y-%m-%d")
                                )
                except Exception as e2:
                    logger.error(f"SCHEDULER: Scraper service also unavailable: {e2}")

        asyncio.run(_async_trigger())
    except Exception as e:
        logger.error(f"SCHEDULER: Failed to trigger scrape: {e}")


@app.on_event("startup")
def startup():
    global running
    running = True
    thread = threading.Thread(target=scheduler_worker, daemon=True)
    thread.start()
    logger.info("Scheduler service started")


@app.on_event("shutdown")
def shutdown():
    global running
    running = False
    logger.info("Scheduler service stopped")


@app.get("/")
def health():
    return {
        "status": "ok",
        "service": "Dice Scraper Scheduler",
        "version": "2.0",
        "last_run": scheduler_state.get("last_scheduled_run_date"),
        "enabled": scraper_config.get("schedule_enabled"),
        "schedule_time": scraper_config.get("schedule_time"),
    }


@app.get("/status")
def get_status(x_api_key: str = Header(None)):
    check_auth(x_api_key)
    with scheduler_lock:
        return {
            "last_run_date": scheduler_state["last_scheduled_run_date"],
            "enabled": scraper_config.get("schedule_enabled"),
            "schedule_time": scraper_config.get("schedule_time"),
            "target_today": scraper_config.get("schedule_time")
            if scraper_config.get("schedule_enabled")
            else None,
        }


@app.post("/trigger-now")
def trigger_now(x_api_key: str = Header(None)):
    check_auth(x_api_key)
    _trigger_scrape("manual")
    return {"message": "Scrape triggered"}


if __name__ == "__main__":
    p = int(os.environ.get("SCHEDULER_PORT", 8002))
    uvicorn.run(app, host="0.0.0.0", port=p)
