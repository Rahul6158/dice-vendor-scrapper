import sys
import os

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

import time
import threading
import asyncio
from datetime import datetime
from fastapi import FastAPI, BackgroundTasks, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from services.common import logger, app_state, scraper_config, API_KEY
from services.common.sheets import SheetManager
from services.scraper.service import run_pipeline_async, DiceScraper

app = FastAPI(title="Dice Scraper Worker Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

running_tasks = {}
task_lock = threading.Lock()


def check_auth(x_api_key: str):
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(
            status_code=401, detail="Invalid or missing X-API-Key header"
        )


@app.get("/")
def health():
    return {"status": "ok", "service": "Dice Scraper Worker", "version": "2.0"}


@app.get("/status")
def get_status(x_api_key: str = Header(None)):
    check_auth(x_api_key)
    return app_state.to_dict()


@app.post("/run")
async def run_scrape(
    payload: dict = None,
    x_api_key: str = Header(None),
    background_tasks: BackgroundTasks = None,
):
    check_auth(x_api_key)

    if app_state.status in ("running", "starting"):
        return {"status": "error", "message": "Scraper already running"}

    config_override = payload.get("config") if payload else None
    task_id = f"scrape_{int(time.time())}"

    app_state.update(
        status="running",
        error=None,
        task="Initializing",
        progress=0,
        stop_requested=False,
    )

    asyncio.create_task(_run_pipeline_background(task_id, config_override))

    return {"status": "started", "task_id": task_id}


async def _run_pipeline_background(task_id: str, config_override: dict = None):
    try:
        result = await run_pipeline_async(config_override)
        with task_lock:
            running_tasks[task_id] = result
        logger.info(f"Pipeline {task_id} completed: {result}")
    except Exception as e:
        logger.error(f"Pipeline {task_id} failed: {e}")
        app_state.update(status="failed", error=str(e))
        with task_lock:
            running_tasks[task_id] = {"status": "failed", "error": str(e)}


@app.post("/stop")
def stop_scrape(x_api_key: str = Header(None)):
    check_auth(x_api_key)
    if app_state.status in ("running", "starting"):
        app_state.update(stop_requested=True)
        return {"message": "Stop requested"}
    return {"message": "Scraper is not running"}


@app.get("/tasks/{task_id}")
def get_task_status(task_id: str, x_api_key: str = Header(None)):
    check_auth(x_api_key)
    with task_lock:
        if task_id in running_tasks:
            return {"task_id": task_id, "result": running_tasks[task_id]}
    return {"task_id": task_id, "status": "not_found"}


if __name__ == "__main__":
    p = int(os.environ.get("SCRAPER_PORT", 8001))
    uvicorn.run(app, host="0.0.0.0", port=p)
