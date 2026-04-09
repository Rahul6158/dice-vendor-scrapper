# Dice Job Scraper V5

A high-performance scraping pipeline that automates the collection and cleaning of job data from Dice.com, integrated directly with Google Sheets.

## 📊 Spreadsheet Structure

The system uses a set of specific tabs in Google Sheets to manage inputs and outputs. Both pipelines follow a **Search -> Store -> Scrape** flow.

### 1. Active Vendor Pipeline

| Purpose                         | Sheet Name              | Expected Columns                      |
| :------------------------------ | :---------------------- | :------------------------------------ |
| **Input Source**          | `input-active`        | `Vendor Name`, `Dice Search Link` |
| **Intermediate Tracking** | `active-dice-jobs`    | `dice_search_url`, `job_url`      |
| **Final Details**         | `active-scraped-data` | Full Cleaned Job Details (11 columns) |

### 2. Inactive Vendor Pipeline

| Purpose                         | Sheet Name                | Expected Columns                                      |
| :------------------------------ | :------------------------ | :---------------------------------------------------- |
| **Input Source**          | `input-inactive`        | `VENDOR NAME`, `Dice Job Link` (Flexible headers) |
| **Intermediate Tracking** | `inactive-dice-jobs`    | `dice_search_url`, `job_url`                      |
| **Final Details**         | `inactive-scraped-data` | Full Cleaned Job Details (11 columns)                 |

> [!TIP]
> **Flexible Header Matching:** The `input-inactive` sheet is configured with flexible matching. It will correctly recognize either `VENDOR NAME` or `Vendor Name`, and either `Dice Job Link` or `Dice Search Link`.

---

## 🚀 Workflow Overview

The system operates in three stages:

1. **Data Ingestion (Input)**: The script reads search criteria from the input tabs listed above.
2. **Search & Filter**: For each vendor link, the script automatically appends `filters.postedDate=ONE` to ensure only jobs from the **past 24 hours** are processed.
3. **URL Tracking (Intermediate)**: New job URLs are added to their respective tracking sheets to ensure we never scrape the same job twice.
4. **Detail Scraping & Cleaning (Output)**: The script visits each new URL, extracts key data, and stores the final result in the scraped-data sheets.

---

## 🛠 Setup & Installation

### 1. Prerequisites

- Python 3.12+
- Google Cloud Service Account Credentials (`.json` file).

### 2. Dependencies

Install the required Python libraries:

```bash
pip install gspread google-auth requests beautifulsoup4 pandas
```

### 3. Google Cloud Configuration

1. **Enable APIs**: Visit the Google Cloud Console and enable both the **Google Sheets API** and the **Google Drive API**.
2. **Share the Sheet**: Open your Google Sheet and share it with the `client_email` found in your credentials JSON:
   - `sheet-access@gen-lang-client-0722398599.iam.gserviceaccount.com`
   - Permission: **Editor**.

---

## 💻 Usage

Run the master controller script:

```powershell
python 3.py
```

### Script Components:

- **`3.py`**: The master controller handling the Google Sheets sync and the full 24h workflow.
- **`1.py`**: Original script for local CSV-based search scraping (Legacy).
- **`2.py`**: Original script for local CSV-based job detail scraping (Legacy).
- **`api.py`**: FastAPI wrapper (Optional) for integrating the scraper with tools like n8n.

---

## 📊 Output Column Mapping

The final sheets contain the following 11 columns in this exact order:

| Column | Name               | Description                          |
| :----- | :----------------- | :----------------------------------- |
| A      | `title`          | Job Title (H1 or JSON-LD)            |
| B      | `company`        | Hiring Company Name                  |
| C      | `location`       | City, State or Remote                |
| D      | `salary`         | Salary range or hourly rate          |
| E      | `posted_date`    | ISO Timestamp of the post            |
| F      | `job_type`       | Full-time, Contract, etc.            |
| G      | `workplace_type` | Remote, Hybrid, or On-site           |
| H      | `description`    | Full plain-text description          |
| I      | `url`            | Permanent Dice URL                   |
| J      | `keyword`        | The search link used for retrieval   |
| K      | `scraped_at`     | Timestamp of when the data was saved |

---

* ⚠️ Notes

- **Dice Anti-Bot**: The script uses pre-configured cookies and headers to minimize blocking.
- **Time Window**: The "Past 24 Hours" filter is forced by the script to capture only the freshest listings.
