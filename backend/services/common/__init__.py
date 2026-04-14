import os
import logging
import re
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
import threading

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("DiceScraper")

SERVICE_ACCOUNT_FILE = os.getenv(
    "GSHEET_CREDS_FILE", "gen-lang-client-0722398599-1c103e9e40e4.json"
)
SPREADSHEET_ID = os.getenv(
    "GSHEET_SPREADSHEET_ID", "18wwnvgoTpAPiqNgaugV1B6fl7zj4bhv-Dww6H5SkRjQ"
)
API_KEY = os.getenv("SCRAPER_API_KEY")
SCRAPE_COOLDOWN = 300

MAX_SEARCH_PAGES = 30
REQUEST_TIMEOUT = 30
MAX_WORKERS = 3
BATCH_SIZE = 50
MAX_RETRIES = 3
PIPELINE_TIMEOUT = 3600

HEADERS = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "accept-language": "en-IN,en;q=0.9,te-IN;q=0.8,te;q=0.7,en-GB;q=0.6,en-US;q=0.5",
    "cache-control": "max-age=0",
    "priority": "u=0, i",
    "sec-ch-ua": '"Chromium";v="146", "Not-A.Brand";v="24", "Google Chrome";v="146"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "document",
    "sec-fetch-mode": "navigate",
    "sec-fetch-site": "none",
    "sec-fetch-user": "?1",
    "upgrade-insecure-requests": "1",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
}

OUTPUT_COLUMNS = [
    "title",
    "company",
    "location",
    "salary",
    "posted_date",
    "job_type",
    "workplace_type",
    "description",
    "skills",
    "experience_required",
    "url",
    "keyword",
    "scraped_at",
]

JD_RE = re.compile(
    r"https://www\.dice\.com/job-detail/"
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    re.I,
)
JD_REL_RE = re.compile(
    r"/job-detail/"
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    re.I,
)

DATE_RANGE_MAP = {
    "ONE": "Last 24 hours",
    "THREE": "Last 3 days",
    "SEVEN": "Last 7 days",
    "THIRTY": "Last 30 days",
}


@dataclass
class AppState:
    status: str = "idle"
    last_run_time: int = 0
    last_run_str: Optional[str] = None
    current_task: Optional[str] = None
    progress: int = 0
    error: Optional[str] = None
    last_active_count: int = 0
    last_inactive_count: int = 0
    last_run_duration: int = 0
    pages_processed: int = 0
    failed_requests: int = 0
    stop_requested: bool = False

    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def update(self, **kwargs):
        with self._lock:
            for key, val in kwargs.items():
                if hasattr(self, key):
                    setattr(self, key, val)
            if "last_run_at" in kwargs:
                self.last_run_time = kwargs["last_run_at"]
                self.last_run_str = datetime.fromtimestamp(
                    kwargs["last_run_at"]
                ).strftime("%Y-%m-%d %H:%M:%S")

    def to_dict(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "status": self.status,
                "last_run_time": self.last_run_time,
                "last_run_str": self.last_run_str,
                "current_task": self.current_task,
                "progress": self.progress,
                "error": self.error,
                "last_active_count": self.last_active_count,
                "last_inactive_count": self.last_inactive_count,
                "last_run_duration": self.last_run_duration,
                "pages_processed": self.pages_processed,
                "failed_requests": self.failed_requests,
                "stop_requested": self.stop_requested,
            }


scraper_config = {
    "date_range": "ONE",
    "date_range_label": "Last 24 hours",
    "max_search_pages": MAX_SEARCH_PAGES,
    "max_workers": MAX_WORKERS,
    "request_timeout": REQUEST_TIMEOUT,
    "scrape_cooldown": SCRAPE_COOLDOWN,
    "schedule_enabled": True,
    "schedule_time": "08:30",
}

app_state = AppState()
