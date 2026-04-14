import os
import logging
import re
from datetime import datetime

# --- LOGGING ---
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("DiceScraper")

# --- CONFIGURATION ---
SERVICE_ACCOUNT_FILE = os.getenv("GSHEET_CREDS_FILE", "gen-lang-client-0722398599-1c103e9e40e4.json")
SPREADSHEET_ID = os.getenv("GSHEET_SPREADSHEET_ID", "18wwnvgoTpAPiqNgaugV1B6fl7zj4bhv-Dww6H5SkRjQ")
API_KEY = os.getenv("SCRAPER_API_KEY") 
SCRAPE_COOLDOWN = 300 

# --- SCRAPER PARAMETERS ---
MAX_SEARCH_PAGES = 30         # Enough pages for any vendor's 24-hour postings
REQUEST_TIMEOUT = 30
MAX_WORKERS = 3            
BATCH_SIZE = 50            
MAX_RETRIES = 3
PIPELINE_TIMEOUT = 3600   

# Full browser fingerprint — matches legacy scraper headers that bypassed Dice bot detection
HEADERS = {
    'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'accept-language': 'en-IN,en;q=0.9,te-IN;q=0.8,te;q=0.7,en-GB;q=0.6,en-US;q=0.5',
    'cache-control': 'max-age=0',
    'priority': 'u=0, i',
    'sec-ch-ua': '"Chromium";v="146", "Not-A.Brand";v="24", "Google Chrome";v="146"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    'sec-fetch-dest': 'document',
    'sec-fetch-mode': 'navigate',
    'sec-fetch-site': 'none',
    'sec-fetch-user': '?1',
    'upgrade-insecure-requests': '1',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36',
}

OUTPUT_COLUMNS = [
    'title', 'company', 'location', 'salary', 'posted_date', 
    'job_type', 'workplace_type', 'description', 'skills', 'experience_required', 'url', 'keyword', 'scraped_at'
]

# Compiled Regex — strict UUID format to match only real Dice job-detail URLs
JD_RE = re.compile(
    r'https://www\.dice\.com/job-detail/'
    r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',
    re.I
)
JD_REL_RE = re.compile(
    r'/job-detail/'
    r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',
    re.I
)
