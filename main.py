import json
import os
import re
import time
import random
import traceback
import threading
import logging
from datetime import datetime
from urllib.parse import parse_qsl, urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed

import gspread
import requests
from requests.adapters import HTTPAdapter
from google.oauth2.service_account import Credentials
from google.auth.transport.requests import Request
from bs4 import BeautifulSoup
from fastapi import FastAPI, BackgroundTasks, HTTPException, Header
import uvicorn

# --- LOGGING ---
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("DiceScraper")

# --- CONFIGURATION (Environment Driven) ---
SERVICE_ACCOUNT_FILE = os.getenv("GSHEET_CREDS_FILE", "gen-lang-client-0722398599-1c103e9e40e4.json")
SPREADSHEET_ID = os.getenv("GSHEET_SPREADSHEET_ID", "18wwnvgoTpAPiqNgaugV1B6fl7zj4bhv-Dww6H5SkRjQ")
API_KEY = os.getenv("SCRAPER_API_KEY") 
SCRAPE_COOLDOWN = 300 

if not API_KEY:
    logger.warning("SCRAPER_API_KEY not set — API endpoints are currently UNPROTECTED.")

if not SPREADSHEET_ID:
    logger.error("GSHEET_SPREADSHEET_ID environment variable is MISSING. Pipeline will fail.")

# --- SCRAPER PARAMETERS ---
MAX_SEARCH_PAGES = 5
REQUEST_TIMEOUT = 30
MAX_WORKERS = 3           
BATCH_SIZE = 50           
MAX_RETRIES = 3
PIPELINE_TIMEOUT = 3600   

HEADERS = {
    'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'accept-language': 'en-IN,en;q=0.9,te-IN;q=0.8,te;q=0.7,en-GB;q=0.6,en-US;q=0.5',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
}

# Column structure for all scraped job data
OUTPUT_COLUMNS = [
    'title', 'company', 'location', 'salary', 'posted_date', 
    'job_type', 'workplace_type', 'description', 'url', 'keyword', 'scraped_at'
]

# Compiled Regex for Dice job URL extraction
_JD_RE = re.compile(r'https://www\.dice\.com/job-detail/[0-9a-f\-]+', re.I)
_JD_REL_RE = re.compile(r'/job-detail/[0-9a-f\-]+', re.I)

# --- GLOBAL API STATE ---
state_lock = threading.Lock()
app_state = {
    "status": "idle", 
    "last_run_time": 0, 
    "last_run_str": None, 
    "current_task": None, 
    "progress": 0, 
    "error": None
}

def update_state(**kwargs):
    """
    Thread-safe update of the API state. 
    Acceptant of None values to allow clearing fields (like error).
    """
    with state_lock:
        if "status" in kwargs:
            app_state["status"] = kwargs["status"]
        if "task" in kwargs:
            app_state["current_task"] = kwargs["task"]
        if "progress" in kwargs:
            app_state["progress"] = kwargs["progress"]
        if "error" in kwargs:
            app_state["error"] = kwargs["error"]
        if "last_run_at" in kwargs:
            ts = kwargs["last_run_at"]
            app_state["last_run_time"] = ts
            app_state["last_run_str"] = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")

def check_auth(x_api_key: str):
    """Check X-API-Key header against SCRAPER_API_KEY environment variable"""
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key header")

# --- GOOGLE SHEETS CORE ---
class SheetManager:
    def __init__(self, service_account_file, spreadsheet_id):
        self.scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        self.sa_file = service_account_file
        self.spreadsheet_id = spreadsheet_id
        
        if not os.path.exists(self.sa_file):
            raise FileNotFoundError(f"Service account file not found: {self.sa_file}")
            
        self.creds = Credentials.from_service_account_file(self.sa_file, scopes=self.scopes)
        self.client = gspread.authorize(self.creds)
        self.sh = self.client.open_by_key(self.spreadsheet_id)
        # Lock ensures thread-safe Google Sheets API operations across workers
        self.api_lock = threading.Lock()

    def refresh_if_needed(self):
        """Ensures OAuth credentials haven't expired using internal valid check"""
        if not self.creds.valid:
            logger.info("Refreshing Google credentials...")
            self.creds.refresh(Request())
            self.client = gspread.authorize(self.creds)
            self.sh = self.client.open_by_key(self.spreadsheet_id)

    def get_all_records(self, sheet_name):
        with self.api_lock:
            self.refresh_if_needed()
            return self.sh.worksheet(sheet_name).get_all_records()

    def append_rows(self, sheet_name, rows):
        """Append rows to sheet with retry logic & non-blocking locks"""
        if not rows:
            return
        logger.info(f"  Uploading {len(rows)} rows to {sheet_name}...")
        for attempt in range(MAX_RETRIES):
            try:
                # Lock only during individual API calls to maximize thread concurrency
                with self.api_lock:
                    self.refresh_if_needed()
                    wks = self.sh.worksheet(sheet_name)
                    wks.append_rows(rows)
                return
            except Exception as e:
                wait = (2 ** attempt) + random.uniform(0.1, 0.5)
                logger.warning(f"    Sheets API Error (attempt {attempt+1}): {e}. Retrying in {wait:.1f}s...")
                time.sleep(wait)

    def get_column_values(self, sheet_name, col_index):
        with self.api_lock:
            self.refresh_if_needed()
            return self.sh.worksheet(sheet_name).col_values(col_index)

    def ensure_headers(self, sheet_name, headers):
        with self.api_lock:
            self.refresh_if_needed()
            wks = self.sh.worksheet(sheet_name)
            if not wks.row_values(1):
                wks.append_row(headers)
                logger.info(f"Initialized headers for {sheet_name}")

# --- SCRAPER CORE ---
class DiceScraper:
    def __init__(self, sheet_manager):
        self.sm = sheet_manager
        self.thread_local = threading.local()
        # Protects URL deduplication set across search worker threads
        self.url_lock = threading.Lock()
        self.start_time = time.time()
        
        # Sequentially prepare sheet structure at startup
        self.sm.ensure_headers('active-dice-jobs', ['dice_search_url', 'job_url'])
        self.sm.ensure_headers('inactive-dice-jobs', ['dice_search_url', 'job_url'])
        self.sm.ensure_headers('active-scraped-data', OUTPUT_COLUMNS)
        self.sm.ensure_headers('inactive-scraped-data', OUTPUT_COLUMNS)

    def _get_session(self):
        """Thread-local session for pool connection reuse"""
        if not hasattr(self.thread_local, "session"):
            session = requests.Session()
            session.headers.update(HEADERS)
            adapter = HTTPAdapter(pool_connections=MAX_WORKERS, pool_maxsize=MAX_WORKERS * 2)
            session.mount("https://", adapter)
            session.mount("http://", adapter)
            self.thread_local.session = session
        return self.thread_local.session

    def _safe_request(self, url, params=None, referer=None):
        if (time.time() - self.start_time) > PIPELINE_TIMEOUT:
            raise TimeoutError("Global pipeline timeout reached.")
        
        session = self._get_session()
        if referer:
            session.headers['Referer'] = referer
        else:
            session.headers.pop('Referer', None)

        for attempt in range(MAX_RETRIES):
            try:
                resp = session.get(url, params=params, timeout=REQUEST_TIMEOUT)
                resp.raise_for_status()
                return resp
            except Exception as e:
                wait = (2 ** attempt) + random.uniform(0.5, 1.5)
                # Extra exponential backoff for rate limiting response codes
                if hasattr(e, 'response') and e.response is not None:
                    if e.response.status_code in (429, 503):
                        logger.warning(f"      Rate-limited (429/503) on {url}. Applying extra backoff.")
                        wait += 10
                logger.warning(f"      Request failed ({url}): {e}. Retrying in {wait:.1f}s...")
                time.sleep(wait)
        return None

    def _extract_job_urls(self, html):
        """Finds all standard Dice job URLs from the page source"""
        urls = _JD_RE.findall(html)
        if not urls:
            urls = ['https://www.dice.com' + m for m in _JD_REL_RE.findall(html)]
        return list(dict.fromkeys(urls))

    def _parse_job_detail(self, html, url, search_url):
        soup = BeautifulSoup(html, 'html.parser')
        ld_data = {}
        # Scrape rich JSON-LD data if available
        for script in soup.find_all('script', type='application/ld+json'):
            try:
                data = json.loads(script.string)
                if isinstance(data, dict) and data.get('@type') == 'JobPosting':
                    ld_data = data
                    break
            except Exception as e:
                logger.debug(f"JSON-LD Parsing skipped: {e}")

        # Basic detail extraction
        title_tag = soup.find('h1')
        title = title_tag.get_text(strip=True) if title_tag else ld_data.get('title', 'Unknown Title')
        comp_tag = soup.find('a', {'data-wa-click': 'djv-job-company-profile-click'})
        company = comp_tag.get_text(strip=True) if comp_tag else ld_data.get('hiringOrganization', {}).get('name', 'N/A')
        
        loc, emp_type, work_mode, salary = '', '', '', ''
        header = soup.find('div', {'data-testid': 'job-detail-header-card'})
        if header:
            loc_s = header.find('span', class_=re.compile(r'order-3'))
            if loc_s:
                loc = loc_s.get_text(strip=True)
            for b in header.find_all('div', class_='SeuiInfoBadge'):
                t = b.get_text(strip=True)
                if any(x in t.lower() for x in ('year', 'hour', 'usd', '$')):
                    salary = t
                elif t in ('On-site', 'Remote', 'Hybrid'):
                    work_mode = t
                elif any(x in t.lower() for x in ('time', 'contract')):
                    emp_type = t

        desc_div = soup.find('div', class_='job-detail-description-module')
        description = desc_div.get_text(separator=' ', strip=True) if desc_div else "No description available."
        
        return {
            'title': title, 
            'company': company, 
            'location': loc or ld_data.get('jobLocation', {}).get('address', {}).get('addressLocality', ''),
            'salary': salary or ld_data.get('baseSalary', {}).get('name', ''), 
            'posted_date': ld_data.get('datePosted', ''),
            'job_type': emp_type or ld_data.get('employmentType', ''), 
            'workplace_type': work_mode,
            'description': description, 
            'url': url, 
            'keyword': search_url,
            'scraped_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

    def _scrape_single_search(self, row, existing_urls):
        search_url = row.get('Dice Search Link') or row.get('Dice Job Link')
        if not search_url:
            return []
            
        # Ensure fresh postings filter is present
        if 'filters.postedDate=' not in search_url:
            search_url += ('&' if '?' in search_url else '?') + 'filters.postedDate=ONE'

        parsed = urlparse(search_url)
        qs = dict(parse_qsl(parsed.query, keep_blank_values=True))
        base = f'{parsed.scheme}://{parsed.netloc}{parsed.path or "/jobs"}'
        
        found_links = []
        for page in range(1, MAX_SEARCH_PAGES + 1):
            resp = self._safe_request(base, params={**qs, 'page': str(page)})
            if not resp:
                break
            urls = self._extract_job_urls(resp.text)
            if not urls:
                break
                
            new_in_page = 0
            with self.url_lock: # Shared Set Deduplication
                for url in urls:
                    if url not in existing_urls:
                        found_links.append([search_url, url])
                        existing_urls.add(url)
                        new_in_page += 1
            if new_in_page == 0 and page > 1:
                break
            time.sleep(0.1) # Polite pause
        return found_links

    def scrape_search_to_dice_jobs(self, input_sheet, output_sheet, base_progress=0):
        logger.info(f"--- SEARCHING: {input_sheet} ---")
        inputs = self.sm.get_all_records(input_sheet)
        existing_rows = self.sm.get_column_values(output_sheet, 2)
        # Skip header explicitly in existing URLs tracking
        existing_urls = set(existing_rows[1:]) if len(existing_rows) > 1 else set()
        
        all_new = []
        total_inp = max(len(inputs), 1)
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {executor.submit(self._scrape_single_search, r, existing_urls): r for r in inputs}
            for i, f in enumerate(as_completed(futures), 1):
                try:
                    all_new.extend(f.result())
                except Exception as e:
                    logger.error(f"Search failure: {e}")
                update_state(progress=base_progress + int((i / total_inp) * 25))
        
        if all_new:
            for start in range(0, len(all_new), BATCH_SIZE):
                self.sm.append_rows(output_sheet, all_new[start : start + BATCH_SIZE])
                time.sleep(1)
        return all_new

    def scrape_job_details_to_output(self, job_links, target_sheet, base_progress=0, processed_urls=None):
        """
        processed_urls: Global deduplication set to avoid cross-flow redundant scrapes.
        Note: The as_completed loop is safe for set writes here without additional locks.
        """
        unique_map = {}
        for s_url, j_url in job_links:
            if j_url not in unique_map:
                if processed_urls is not None and j_url in processed_urls:
                    continue
                unique_map[j_url] = s_url
        
        unique_links = [[s, j] for j, s in unique_map.items()]
        
        if not unique_links:
            logger.info(f"No new details to scrape for {target_sheet}.")
            return 0

        logger.info(f"--- SCRAPING DETAILS: {len(unique_links)} unique jobs ---")
        results_buffer = []
        total_q = max(len(unique_links), 1)
        scraped_count = 0
        
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            task_map = {executor.submit(self._scrape_single_job, s, u): u for s, u in unique_links}
            for i, f in enumerate(as_completed(task_map), 1):
                url = task_map[f]
                # Track URL regardless of scraper final result
                if processed_urls is not None:
                    processed_urls.add(url)
                try:
                    res = f.result()
                    if res:
                        results_buffer.append(res)
                        scraped_count += 1
                except Exception as e:
                    logger.error(f"Scrape failure for {url}: {e}")
                
                update_state(progress=base_progress + int((i / total_q) * 25))
                if len(results_buffer) >= BATCH_SIZE:
                    self.sm.append_rows(target_sheet, results_buffer)
                    results_buffer = []
                    time.sleep(1)
            
            if results_buffer:
                self.sm.append_rows(target_sheet, results_buffer)
        return scraped_count

# --- FASTAPI ---
app = FastAPI(title="Dice Scraper Pro API")

def run_pipeline():
    # Pipeline initialization
    update_state(status="running", error=None, task="Initializing", progress=0)
    # Global cross-flow deduplication set
    global_detail_urls = set()
    
    try:
        sm = SheetManager(SERVICE_ACCOUNT_FILE, SPREADSHEET_ID)
        scraper = DiceScraper(sm)
        
        # 1. Active Search
        update_state(task="Active Search")
        a_links = scraper.scrape_search_to_dice_jobs('input-active', 'active-dice-jobs', 0)
        
        # 2. Active Details
        update_state(task="Active Details", progress=25)
        count_a = scraper.scrape_job_details_to_output(a_links, 'active-scraped-data', 25, global_detail_urls)
        
        # 3. Inactive Search
        update_state(task="Inactive Search", progress=50)
        i_links = scraper.scrape_search_to_dice_jobs('input-inactive', 'inactive-dice-jobs', 50)
        
        # 4. Inactive Details
        update_state(task="Inactive Details", progress=75)
        count_i = scraper.scrape_job_details_to_output(i_links, 'inactive-scraped-data', 75, global_detail_urls)
        
        update_state(status="idle", progress=100, task="Completed", last_run_at=time.time(), error=None)
        logger.info(f"Pipeline complete: {count_a} active, {count_i} inactive jobs scraped.")
        
    except Exception as e:
        logger.error(f"Pipeline critical failure: {e}")
        traceback.print_exc()
        update_state(status="failed", error=str(e), last_run_at=time.time())

@app.get("/")
async def health():
    return {"status": "ok", "service": "Dice Scraper Pro"}

@app.get("/status")
async def get_status(x_api_key: str = Header(None)):
    check_auth(x_api_key)
    with state_lock:
        return app_state

@app.post("/scrape")
async def trigger_scrape(background_tasks: BackgroundTasks, x_api_key: str = Header(None)):
    check_auth(x_api_key)
    with state_lock:
        if app_state["status"] == "running":
            return {
                "status": "already_running", 
                "message": "A scrape task is currently in progress."
            }
        
        now = time.time()
        elapsed = now - app_state["last_run_time"]
        if elapsed < SCRAPE_COOLDOWN:
            return {
                "status": "cooldown", 
                "message": f"Cooldown active. Wait {int(SCRAPE_COOLDOWN - elapsed)}s more."
            }
        
        # Slot reserved atomically
        app_state["status"] = "starting"
        app_state["last_run_time"] = now

    background_tasks.add_task(run_pipeline)
    return {
        "status": "started", 
        "message": "The automation pipeline has been triggered in the background."
    }

if __name__ == "__main__":
    p = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=p)
