import json
import re
import time
import random
import threading
import asyncio
import os
import sys
from datetime import datetime
from urllib.parse import parse_qsl, urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Tuple, Callable, Optional, Set

# Ensure proper import path
_backend = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _backend not in sys.path:
    sys.path.insert(0, _backend)

import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
import httpx

from services.common import (
    logger,
    HEADERS,
    MAX_WORKERS,
    MAX_RETRIES,
    REQUEST_TIMEOUT,
    PIPELINE_TIMEOUT,
    MAX_SEARCH_PAGES,
    BATCH_SIZE,
    OUTPUT_COLUMNS,
    JD_RE,
    JD_REL_RE,
    app_state,
    scraper_config,
    SERVICE_ACCOUNT_FILE,
    SPREADSHEET_ID,
)
from services.common.sheets import SheetManager


class DiceScraper:
    def __init__(self, sheet_manager: SheetManager = None, cfg: dict = None):
        self.sm = sheet_manager or SheetManager(SERVICE_ACCOUNT_FILE, SPREADSHEET_ID)
        cfg = cfg or {}
        self.max_search_pages = cfg.get("max_search_pages", MAX_SEARCH_PAGES)
        self.date_range = cfg.get("date_range", "ONE")
        self.max_workers = cfg.get("max_workers", MAX_WORKERS)
        self.req_timeout = cfg.get("request_timeout", REQUEST_TIMEOUT)

        self.thread_local = threading.local()
        self.url_lock = threading.Lock()
        self.start_time = time.time()
        self.pages_processed = 0
        self.failed_requests = 0
        self.update_state_cb = None

        self.sm.ensure_headers("active-dice-jobs", ["dice_search_url", "job_url"])
        self.sm.ensure_headers("inactive-dice-jobs", ["dice_search_url", "job_url"])
        self.sm.ensure_headers("active-scraped-data", OUTPUT_COLUMNS)
        self.sm.ensure_headers("inactive-scraped-data", OUTPUT_COLUMNS)

    def _get_session(self):
        if not hasattr(self.thread_local, "session"):
            session = requests.Session()
            session.headers.update(HEADERS)
            adapter = HTTPAdapter(
                pool_connections=MAX_WORKERS, pool_maxsize=MAX_WORKERS * 2
            )
            session.mount("https://", adapter)
            session.mount("http://", adapter)
            self.thread_local.session = session
        return self.thread_local.session

    def _safe_request(self, url, params=None, referer=None):
        if (time.time() - self.start_time) > PIPELINE_TIMEOUT:
            raise TimeoutError("Global pipeline timeout reached.")

        session = self._get_session()
        if referer:
            session.headers["Referer"] = referer
        else:
            session.headers.pop("Referer", None)

        for attempt in range(MAX_RETRIES):
            try:
                self.pages_processed += 1
                if self.update_state_cb:
                    self.update_state_cb(pages_processed=self.pages_processed)

                resp = session.get(url, params=params, timeout=REQUEST_TIMEOUT)
                resp.raise_for_status()
                return resp
            except Exception as e:
                self.failed_requests += 1
                if self.update_state_cb:
                    self.update_state_cb(failed_requests=self.failed_requests)

                wait = (2**attempt) + random.uniform(0.5, 1.5)
                if hasattr(e, "response") and e.response is not None:
                    if e.response.status_code in (429, 503):
                        logger.warning(f"Rate-limited on {url}. Extra backoff.")
                        wait += 10
                logger.warning(
                    f"Request failed ({url}): {e}. Retrying in {wait:.1f}s..."
                )
                time.sleep(wait)
        return None

    def _extract_job_urls(self, html):
        urls = JD_RE.findall(html)
        if not urls:
            urls = ["https://www.dice.com" + m for m in JD_REL_RE.findall(html)]
        return list(dict.fromkeys(urls))

    def _extract_json_ld(self, soup):
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string)
                if isinstance(data, dict) and data.get("@type") == "JobPosting":
                    return data
            except Exception:
                continue
        return {}

    def _extract_description(self, soup, ld_data):
        ALLOWED_TAGS = {
            "p",
            "br",
            "b",
            "strong",
            "i",
            "em",
            "u",
            "ul",
            "ol",
            "li",
            "h1",
            "h2",
            "h3",
            "h4",
            "h5",
            "a",
            "table",
            "thead",
            "tbody",
            "tr",
            "th",
            "td",
            "hr",
        }

        def sanitize_html(raw_html):
            bs = BeautifulSoup(raw_html, "html.parser")
            for tag in bs.find_all(True):
                if tag.name not in ALLOWED_TAGS:
                    tag.unwrap()
                else:
                    allowed_attrs = ["href"] if tag.name == "a" else []
                    tag.attrs = {
                        k: v for k, v in tag.attrs.items() if k in allowed_attrs
                    }
            return str(bs)

        desc = ld_data.get("description", "")
        if desc:
            if desc.strip().startswith("{") and '"description"' in desc:
                try:
                    inner = json.loads(desc)
                    desc = inner.get("description", desc)
                except Exception:
                    pass
            return sanitize_html(desc)

        desc_div = soup.find("div", class_=lambda c: c and "jobDescription" in c)
        if desc_div:
            return sanitize_html(str(desc_div))

        desc_div = soup.select_one('[data-testid="job-description"]')
        if desc_div:
            return sanitize_html(str(desc_div))

        return "<p>No description available.</p>"

    def _extract_skills_from_page(self, soup):
        skills = []
        META_BADGES = {
            "on-site",
            "remote",
            "hybrid",
            "full time",
            "part time",
            "contract",
            "third party",
        }

        skills_heading = soup.find(
            lambda tag: (
                tag.name in ("h3", "h2", "h4")
                and tag.get_text(strip=True).lower() == "skills"
            )
        )
        if skills_heading:
            skills_ul = skills_heading.find_next_sibling("ul")
            if not skills_ul:
                parent = skills_heading.parent
                if parent:
                    skills_ul = parent.find("ul")
            if skills_ul:
                for badge in skills_ul.find_all("div", class_="SeuiInfoBadge"):
                    inner = badge.find("div")
                    if inner:
                        text = inner.get_text(strip=True)
                        if text and text.lower() not in META_BADGES:
                            skills.append(text)
                if skills:
                    return list(dict.fromkeys(skills))

        for badge in soup.find_all("div", class_="SeuiInfoBadge"):
            inner = badge.find("div")
            if inner:
                text = inner.get_text(strip=True)
                if text and text.lower() not in META_BADGES:
                    skills.append(text)

        return list(dict.fromkeys(skills))

    def _extract_experience(self, text):
        if not text:
            return ""
        match = re.search(r"(\d+)\+?\s+years?", text, re.I)
        return match.group(0) if match else ""

    def _job_dict_to_row(self, job_dict):
        return [str(job_dict.get(col, "")) for col in OUTPUT_COLUMNS]

    def _parse_job_detail(self, html, url, search_url):
        soup = BeautifulSoup(html, "html.parser")
        ld_data = self._extract_json_ld(soup)

        title = ld_data.get("title", "")
        if not title:
            h1 = soup.find("h1")
            title = h1.get_text(strip=True) if h1 else "Unknown Title"

        company = ld_data.get("hiringOrganization", {}).get("name", "")
        if not company:
            comp_tag = soup.find(
                "a", {"data-wa-click": "djv-job-company-profile-click"}
            )
            company = comp_tag.get_text(strip=True) if comp_tag else "N/A"

        emp_types, work_mode, salary = [], "", ""
        header = soup.find("div", {"data-testid": "job-detail-header-card"})

        if header:
            loc_type_badge = header.find(attrs={"data-testid": "locationTypeBadge"})
            if loc_type_badge:
                work_mode = loc_type_badge.get_text(strip=True)

            badge_container = header.find(
                "div", class_=lambda c: c and "order-4" in c.split()
            )
            if badge_container:
                for b in badge_container.find_all("div", class_="SeuiInfoBadge"):
                    t = b.get_text(strip=True)
                    tl = t.lower()
                    if any(
                        x in tl
                        for x in ("usd", "$", "depends on", "per year", "per hour")
                    ):
                        salary = t
                    elif t in ("On-site", "Remote", "Hybrid"):
                        if not work_mode:
                            work_mode = t
                    elif any(
                        x in tl
                        for x in (
                            "full time",
                            "full-time",
                            "part time",
                            "part-time",
                            "contract",
                            "third party",
                            "permanent",
                            "freelance",
                            "w2",
                            "c2c",
                            "corp to corp",
                        )
                    ):
                        emp_types.append(t)

        emp_type = ", ".join(dict.fromkeys(emp_types))

        jl = ld_data.get("jobLocation", {})
        addr = jl.get("address", {}) if isinstance(jl, dict) else {}
        loc = addr.get("addressLocality", "") or addr.get("addressRegion", "")

        if not loc and header:
            order3 = header.find("span", class_=lambda c: c and "order-3" in c.split())
            if order3:
                first_span = order3.find("span")
                if first_span:
                    raw = first_span.get_text(strip=True)
                    loc = re.sub(
                        r"^(?:Hybrid|Remote|On-site)\s+in\s+", "", raw, flags=re.I
                    ).strip()

        if not salary:
            bs = ld_data.get("baseSalary", {})
            if isinstance(bs, dict):
                v = bs.get("value", {})
                if isinstance(v, dict):
                    mn, mx = v.get("minValue", ""), v.get("maxValue", "")
                    cu = bs.get("currency", "USD")
                    unit = v.get("unitText", "")
                    if mn and mx:
                        salary = f"{cu} ${mn} - {mx} {unit}".strip()
                    elif mn:
                        salary = f"{cu} ${mn} {unit}".strip()
                elif v:
                    salary = str(v)

        if not emp_type:
            emp_type = ld_data.get("employmentType", "")

        description = self._extract_description(soup, ld_data)
        skills = self._extract_skills_from_page(soup)
        plain_text = BeautifulSoup(description, "html.parser").get_text(" ", strip=True)
        experience = self._extract_experience(plain_text)

        return {
            "title": title,
            "company": company,
            "location": loc,
            "salary": salary,
            "posted_date": ld_data.get("datePosted", ""),
            "job_type": emp_type,
            "workplace_type": work_mode,
            "description": description,
            "skills": ", ".join(skills),
            "experience_required": experience,
            "url": url,
            "keyword": search_url,
            "scraped_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    def _scrape_single_job(self, search_url, job_url):
        resp = self._safe_request(job_url, referer=search_url)
        if resp:
            return self._parse_job_detail(resp.text, job_url, search_url)
        return None

    def _scrape_single_search(
        self, row, existing_urls, update_state_cb, base_progress, total_inp, current_idx
    ):
        search_url = row.get("Dice Search Link") or row.get("Dice Job Link")
        if not search_url:
            return []

        parsed = urlparse(search_url.strip())
        qs = dict(parse_qsl(parsed.query, keep_blank_values=True))
        qs["filters.postedDate"] = self.date_range
        base = f"{parsed.scheme}://{parsed.netloc}{parsed.path or '/jobs'}"

        logger.info(f"Searching: {base}")
        found_links = []
        total_found = 0
        for page in range(1, self.max_search_pages + 1):
            resp = self._safe_request(base, params={**qs, "page": str(page)})
            if not resp:
                logger.warning(f"Page {page}: no response, stopping.")
                break

            urls = self._extract_job_urls(resp.text)
            if not urls:
                logger.info(f"Page {page}: no job URLs found, stopping.")
                break

            total_found += len(urls)
            new_in_page = 0
            with self.url_lock:
                for url in urls:
                    if url not in existing_urls:
                        found_links.append([search_url, url])
                        existing_urls.add(url)
                        new_in_page += 1

            logger.info(f"Page {page}: {len(urls)} jobs, {new_in_page} new.")

            if new_in_page == 0 and page > 1:
                logger.info(f"No new jobs on page {page}, stopping.")
                break
            time.sleep(0.5)

        if update_state_cb:
            update_state_cb(
                progress=base_progress + int((current_idx / total_inp) * 25)
            )

        logger.info(f"Found {len(found_links)} new URLs from this vendor.")
        return found_links

    def scrape_search_to_dice_jobs(
        self,
        input_sheet,
        output_sheet,
        update_state_cb,
        base_progress=0,
        scraped_sheet=None,
    ):
        self.update_state_cb = update_state_cb
        self.pages_processed = 0
        self.failed_requests = 0

        logger.info(f"--- SEARCHING: {input_sheet} ---")
        inputs = self.sm.get_all_records(input_sheet)

        if scraped_sheet:
            existing_rows = self.sm.get_column_values(scraped_sheet, 11)
            logger.info(
                f"Loaded {max(0, len(existing_rows) - 1)} existing URLs from {scraped_sheet}"
            )
        else:
            existing_rows = self.sm.get_column_values(output_sheet, 2)
        existing_urls = set(existing_rows[1:]) if len(existing_rows) > 1 else set()

        all_new = []
        total_inp = max(len(inputs), 1)
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(
                    self._scrape_single_search,
                    r,
                    existing_urls,
                    update_state_cb,
                    base_progress,
                    total_inp,
                    i,
                ): i
                for i, r in enumerate(inputs, 1)
            }
            for f in as_completed(futures):
                try:
                    all_new.extend(f.result())
                except Exception as e:
                    logger.error(f"Search failure: {e}")

        if all_new:
            for start in range(0, len(all_new), BATCH_SIZE):
                self.sm.append_rows(output_sheet, all_new[start : start + BATCH_SIZE])
                time.sleep(1)
        return all_new

    def scrape_job_details_to_output(
        self,
        job_links,
        target_sheet,
        update_state_cb,
        base_progress=0,
        processed_urls=None,
    ):
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
            task_map = {
                executor.submit(self._scrape_single_job, s, u): u
                for s, u in unique_links
            }
            for i, f in enumerate(as_completed(task_map), 1):
                url = task_map[f]
                if processed_urls is not None:
                    processed_urls.add(url)
                try:
                    res = f.result()
                    if res:
                        results_buffer.append(self._job_dict_to_row(res))
                        scraped_count += 1
                except Exception as e:
                    logger.error(f"Scrape failure for {url}: {e}")

                if update_state_cb:
                    update_state_cb(progress=base_progress + int((i / total_q) * 25))

                if len(results_buffer) >= BATCH_SIZE:
                    self.sm.append_rows(target_sheet, results_buffer)
                    results_buffer = []
                    time.sleep(1)

            if results_buffer:
                self.sm.append_rows(target_sheet, results_buffer)

        return scraped_count


async def run_pipeline_async(config_override: dict = None) -> dict:
    """Run the full scraping pipeline asynchronously for better performance."""
    cfg = config_override or dict(scraper_config)

    def update_state(**kwargs):
        app_state.update(**kwargs)

    update_state(status="running", error=None, task="Initializing", progress=0)
    start_time = time.time()

    try:
        sm = SheetManager(SERVICE_ACCOUNT_FILE, SPREADSHEET_ID)
        scraper = DiceScraper(sm, cfg)

        processed_urls: Set[str] = set()

        update_state(task="Active Discovery", progress=0, stop_requested=False)
        a_links = scraper.scrape_search_to_dice_jobs(
            "input-active", "active-dice-jobs", update_state, 0, "active-scraped-data"
        )

        if app_state.stop_requested:
            update_state(status="idle", task="Stopped by user", progress=0)
            return {"status": "stopped", "active": 0, "inactive": 0}

        update_state(task="Active Details", progress=25)
        count_a = scraper.scrape_job_details_to_output(
            a_links, "active-scraped-data", update_state, 25, processed_urls
        )

        if app_state.stop_requested:
            update_state(status="idle", task="Stopped by user", progress=25)
            return {"status": "stopped", "active": count_a, "inactive": 0}

        update_state(task="Inactive Discovery", progress=50)
        i_links = scraper.scrape_search_to_dice_jobs(
            "input-inactive",
            "inactive-dice-jobs",
            update_state,
            50,
            "inactive-scraped-data",
        )

        if app_state.stop_requested:
            update_state(status="idle", task="Stopped by user", progress=50)
            return {"status": "stopped", "active": count_a, "inactive": 0}

        update_state(task="Inactive Details", progress=75)
        count_i = scraper.scrape_job_details_to_output(
            i_links, "inactive-scraped-data", update_state, 75, processed_urls
        )

        duration = int(time.time() - start_time)
        update_state(
            status="idle",
            progress=100,
            task="Completed",
            last_run_at=time.time(),
            error=None,
            last_active_count=count_a,
            last_inactive_count=count_i,
            last_run_duration=duration,
            stop_requested=False,
        )
        logger.info(
            f"Pipeline complete: {count_a} active, {count_i} inactive jobs scraped."
        )

        return {
            "status": "completed",
            "active": count_a,
            "inactive": count_i,
            "duration": duration,
        }

    except Exception as e:
        logger.error(f"Pipeline critical failure: {e}")
        update_state(status="failed", error=str(e), last_run_at=time.time())
        return {"status": "failed", "error": str(e)}


def run_pipeline_sync(config_override: dict = None) -> dict:
    """Synchronous wrapper for running pipeline in a thread."""
    return asyncio.run(run_pipeline_async(config_override))
