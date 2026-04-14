import os
import random
import time
import threading
import gspread
from google.oauth2.service_account import Credentials
from google.auth.transport.requests import Request
from config import logger, MAX_RETRIES

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
        # Retry the initial connection — Google OAuth can transiently drop on first request
        last_err = None
        for attempt in range(1, 4):
            try:
                self.sh = self.client.open_by_key(self.spreadsheet_id)
                break
            except Exception as e:
                last_err = e
                wait = 3 * attempt
                import time as _time
                logger.warning(f"Google Sheets connection failed (attempt {attempt}/3): {e}. Retrying in {wait}s...")
                _time.sleep(wait)
        else:
            raise ConnectionError(f"Failed to connect to Google Sheets after 3 attempts: {last_err}")
        self.api_lock = threading.Lock()

    def refresh_if_needed(self):
        for attempt in range(3):
            try:
                if not self.creds.valid:
                    logger.info("Refreshing Google credentials...")
                    self.creds.refresh(Request())
                    self.client = gspread.authorize(self.creds)
                    self.sh = self.client.open_by_key(self.spreadsheet_id)
                return
            except Exception as e:
                logger.error(f"Failed to refresh Google credentials (attempt {attempt+1}): {e}")
                if attempt == 2:
                    # Re-initialize as last resort
                    self.client = gspread.authorize(self.creds)
                    self.sh = self.client.open_by_key(self.spreadsheet_id)
                time.sleep(1 + attempt)

    def _execute_with_retry(self, func, *args, **kwargs):
        """Helper to execute gspread operations with retry logic for connection issues."""
        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                with self.api_lock:
                    self.refresh_if_needed()
                    return func(*args, **kwargs)
            except Exception as e:
                last_error = e
                # Check for connection errors specifically
                if "Remote end closed connection" in str(e) or "Connection aborted" in str(e):
                    logger.warning(f"Connection aborted by Google. Re-initializing client (attempt {attempt+1})...")
                    self.client = gspread.authorize(self.creds)
                    self.sh = self.client.open_by_key(self.spreadsheet_id)
                
                wait = (2 ** attempt) + random.uniform(0.1, 0.5)
                time.sleep(wait)
        
        logger.error(f"Persistent failure after {MAX_RETRIES} attempts: {last_error}")
        raise last_error

    def get_all_records(self, sheet_name):
        return self._execute_with_retry(lambda: self.sh.worksheet(sheet_name).get_all_records())

    def get_records_paginated(self, sheet_name, page=1, limit=20):
        wks = self._execute_with_retry(lambda: self.sh.worksheet(sheet_name))
        
        headers = self._execute_with_retry(lambda: wks.row_values(1))
        if not headers:
            return []
            
        start_row = ((page - 1) * limit) + 2
        end_row = start_row + limit - 1
        
        col_letter = chr(64 + len(headers)) if len(headers) <= 26 else 'Z'
        range_str = f"A{start_row}:{col_letter}{end_row}"
        
        data = self._execute_with_retry(lambda: wks.get(range_str))
        
        records = []
        for row in data:
            padded_row = row + [''] * (len(headers) - len(row))
            records.append(dict(zip(headers, padded_row)))
            
        return records

    def append_rows(self, sheet_name, rows):
        if not rows: return
        self._execute_with_retry(lambda: self.sh.worksheet(sheet_name).append_rows(rows))

    def get_column_values(self, sheet_name, col_index):
        return self._execute_with_retry(lambda: self.sh.worksheet(sheet_name).col_values(col_index))

    def ensure_headers(self, sheet_name, headers):
        wks = self._execute_with_retry(lambda: self.sh.worksheet(sheet_name))
        existing_headers = self._execute_with_retry(lambda: wks.row_values(1))
        if not existing_headers:
            self._execute_with_retry(lambda: wks.append_row(headers))
            logger.info(f"Initialized headers for {sheet_name}")
