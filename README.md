# Dice Job Scraper V5

A high-performance scraping pipeline that automates the collection and cleaning of job data from Dice.com, integrated directly with Google Sheets.

## Architecture

The backend uses a **microservices architecture** for better performance, scalability, and fault isolation:

```
backend/
├── services/
│   ├── common/           # Shared config, state, sheets manager
│   │   ├── __init__.py  # AppState, scraper_config, constants
│   │   └── sheets.py     # Google Sheets integration
│   ├── api/              # HTTP API Gateway (port 8000)
│   │   └── main.py       # REST endpoints for frontend
│   ├── scraper/          # Scraping Worker (port 8001)
│   │   ├── main.py       # FastAPI worker service
│   │   └── service.py    # DiceScraper class, async pipeline
│   ├── scheduler/         # Scheduler Service (port 8002)
│   │   └── service.py    # Time-based job scheduling
│   ├── run.py            # Unified entry point
│   └── README.md         # Detailed microservices docs
├── main.py               # Simplified entry (uses services/)
├── scraper.py            # Legacy (deprecated)
├── sheets.py             # Legacy (deprecated)
└── config.py             # Legacy (deprecated)
```

## Services

| Service | Port | Purpose |
|---------|------|---------|
| **API Gateway** | 8000 | REST API for frontend, handles requests/responses |
| **Scraper Worker** | 8001 | Executes scraping jobs, parallel processing |
| **Scheduler** | 8002 | Time-based scheduling, triggers scraper |

## Running Modes

### All-in-One (Default - Recommended for Development)

```bash
cd backend
python main.py
```

All services run in a single process on port 8000.

### Separate Services (Production)

```bash
# Terminal 1 - API Gateway
python backend/services/run.py --service api

# Terminal 2 - Scraper Worker
python backend/services/run.py --service scraper

# Terminal 3 - Scheduler
python backend/services/run.py --service scheduler
```

## Performance Features

- **Async Pipeline**: Non-blocking I/O for faster operations
- **Parallel Processing**: ThreadPoolExecutor for concurrent job scraping
- **Connection Pooling**: Reuses HTTP connections
- **Batch Processing**: 50 jobs per batch to Google Sheets
- **Fault Isolation**: One service failure doesn't crash others

---

## Spreadsheet Structure

The system uses specific tabs in Google Sheets for inputs and outputs.

### 1. Active Vendor Pipeline

| Purpose | Sheet Name | Expected Columns |
|---------|------------|-----------------|
| Input Source | `input-active` | `Vendor Name`, `Dice Search Link` |
| Intermediate Tracking | `active-dice-jobs` | `dice_search_url`, `job_url` |
| Final Details | `active-scraped-data` | Full Cleaned Job Details |

### 2. Inactive Vendor Pipeline

| Purpose | Sheet Name | Expected Columns |
|---------|------------|-----------------|
| Input Source | `input-inactive` | `VENDOR NAME`, `Dice Job Link` |
| Intermediate Tracking | `inactive-dice-jobs` | `dice_search_url`, `job_url` |
| Final Details | `inactive-scraped-data` | Full Cleaned Job Details |

---

## Setup & Installation

### 1. Prerequisites

- Python 3.11+
- Google Cloud Service Account Credentials (`.json` file)

### 2. Dependencies

```bash
pip install -r requirements.txt
```

### 3. Environment Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `GSHEET_SPREADSHEET_ID` | Google Sheet ID | **Required** |
| `SCRAPER_API_KEY` | API authentication key | Optional |
| `GSHEET_CREDS_FILE` | Service account JSON path | `gen-lang-client-...json` |
| `PORT` | API Gateway port | `8000` |
| `SCRAPER_PORT` | Scraper service port | `8001` |
| `SCHEDULER_PORT` | Scheduler service port | `8002` |

### 4. Google Cloud Configuration

1. Enable **Google Sheets API** and **Google Drive API** in Google Cloud Console
2. Share your Google Sheet with the `client_email` from your credentials JSON
3. Grant **Editor** permission

---

## Frontend Dashboard

Modern React + Vite dashboard with real-time updates.

### Features
- **Mission Control**: Real-time stats, scheduler status
- **Job Board**: Searchable feed of scraped listings
- **Settings Hub**: Configurable scraper parameters
- **Progress Tracking**: Live progress bar during scraping

### Running the Dashboard

```bash
cd frontend
npm install
npm run dev
```

Dashboard available at `http://localhost:5173`

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Health check |
| GET | `/status` | Current pipeline status |
| GET | `/jobs` | Paginated job listings |
| GET | `/stats` | Dashboard statistics |
| GET | `/settings` | Current scraper settings |
| POST | `/settings` | Update scraper settings |
| POST | `/trigger` | Start scraping pipeline |
| POST | `/stop` | Stop running pipeline |

All endpoints require `X-API-Key` header (if configured).

---

## Output Columns

| Column | Name | Description |
|--------|------|-------------|
| A | `title` | Job Title |
| B | `company` | Hiring Company |
| C | `location` | City, State or Remote |
| D | `salary` | Salary range or rate |
| E | `posted_date` | ISO timestamp |
| F | `job_type` | Full-time, Contract, etc. |
| G | `workplace_type` | Remote, Hybrid, On-site |
| H | `description` | Full job description (HTML) |
| I | `skills` | Extracted skills |
| J | `experience_required` | Years of experience |
| K | `url` | Permanent Dice URL |
| L | `keyword` | Search link used |
| M | `scraped_at` | Scrape timestamp |

---

## Docker Deployment

```bash
# Build
cd backend
docker build -t dice-scraper .

# Run (all-in-one)
docker run -p 8000:8000 --env-file .env dice-scraper
```

---

## Notes

- **Dice Anti-Bot**: Pre-configured headers minimize blocking
- **24-Hour Filter**: Forces "Past 24 Hours" for fresh listings
- **Scheduler**: Runs once daily at configured time (default 08:30)
