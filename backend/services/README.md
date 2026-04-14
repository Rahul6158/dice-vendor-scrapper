# Microservices Architecture

## Overview

The Dice Scraper backend has been restructured into microservices for better performance and scalability.

## Services

### 1. API Gateway (`services/api/`)
- **Port**: 8000 (default)
- **Purpose**: HTTP API endpoint for frontend communication
- **Responsibilities**:
  - Status, jobs, stats, settings endpoints
  - Trigger/stop scraping commands
  - Authentication

### 2. Scraper Worker (`services/scraper/`)
- **Port**: 8001
- **Purpose**: Handles all scraping operations
- **Responsibilities**:
  - Job discovery from Dice
  - Job detail extraction
  - Parallel processing with ThreadPoolExecutor
  - Async pipeline execution

### 3. Scheduler (`services/scheduler/`)
- **Port**: 8002
- **Purpose**: Time-based scheduling
- **Responsibilities**:
  - Runs scraping at configured times
  - Retry logic when scraper is busy
  - Triggers via HTTP to API or Scraper service

### 4. Common (`services/common/`)
- **Purpose**: Shared code between all services
- **Contains**:
  - Configuration
  - State management (AppState)
  - Google Sheets manager

## Running Modes

### All-in-One (Default)
```bash
python backend/main.py
# or
python backend/services/run.py
```
Runs everything in a single process on port 8000.

### Separate Services (Production)
```bash
# Terminal 1 - API Gateway
python backend/services/run.py --service api

# Terminal 2 - Scraper Worker
python backend/services/run.py --service scraper

# Terminal 3 - Scheduler
python backend/services/run.py --service scheduler
```

### Docker Compose (Recommended for Production)
```yaml
services:
  api:
    build: .
    command: python services/run.py --service api
    ports:
      - "8000:8000"
    environment:
      - SCRAPER_API_KEY=your_key
  
  scraper:
    build: .
    command: python services/run.py --service scraper
    ports:
      - "8001:8001"
    environment:
      - SCRAPER_API_KEY=your_key
  
  scheduler:
    build: .
    command: python services/run.py --service scheduler
    ports:
      - "8002:8002"
    environment:
      - API_SERVICE_URL=http://api:8000
      - SCRAPER_SERVICE_URL=http://scraper:8001
      - SCRAPER_API_KEY=your_key
```

## Performance Benefits

1. **Independent Scaling**: Each service can be scaled based on load
2. **Fault Isolation**: One service failure doesn't crash others
3. **Parallel Processing**: Scraper can run multiple workers
4. **Async Operations**: Uses asyncio for non-blocking I/O
5. **Connection Pooling**: Reuses HTTP connections between services

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | 8000 | API Gateway port |
| `SCRAPER_PORT` | 8001 | Scraper service port |
| `SCHEDULER_PORT` | 8002 | Scheduler service port |
| `API_SERVICE_URL` | http://localhost:8000 | Internal API URL |
| `SCRAPER_SERVICE_URL` | http://localhost:8001 | Internal scraper URL |
| `SCRAPER_API_KEY` | None | API authentication key |
| `GSHEET_CREDS_FILE` | *.json | Google service account file |
| `GSHEET_SPREADSHEET_ID` | * | Google Sheets ID |
