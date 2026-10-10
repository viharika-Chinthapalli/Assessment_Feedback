"""
Extract question content from Django admin by question_id and write it to Google Sheets.

Usage:
  python extract_question_content.py --sheet-url "https://docs.google.com/spreadsheets/d/.../edit" --sheet-name "Sheet1"

Or run interactively (prompts for sheet URL and sub-sheet name).

Sheet layout:
  - Row 1 = headers
  - Column 1 (or header "question_id") = question IDs
  - Header "question_content" = destination column for extracted content
"""

from __future__ import annotations

import argparse
import os
import re
import time
from pathlib import Path

from dotenv import load_dotenv
from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials as UserCredentials
from googleapiclient.discovery import build
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

OAUTH_TOKEN_JSON = BASE_DIR / "google-oauth-token.json"
OAUTH_CLIENT_JSON = BASE_DIR / "oauth-client.json"
OAUTH_PORT = int(os.environ.get("GOOGLE_OAUTH_PORT", "8080"))
SHEETS_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

LOGIN_URL = os.environ.get(
    "ASSESSMENT_ADMIN_LOGIN_URL",
    "https://nxtwave-assessments-backend-topin-prod-apis.ccbp.in/admin/login/?next=/admin/",
).strip()
QUESTION_LIST_URL = os.environ.get(
    "ASSESSMENT_QUESTION_LIST_URL",
    "https://nxtwave-assessments-backend-topin-prod-apis.ccbp.in/admin/nkb_question/question/",
).strip()
WAIT_TIME = int(os.environ.get("ASSESSMENT_SELENIUM_WAIT", "20"))

QUESTION_ID_HEADERS = {"question_id", "question id", "qid", "id"}
QUESTION_CONTENT_HEADERS = {"question_content", "question content", "content"}


def _admin_creds() -> tuple[str, str]:
    username = os.environ.get("ASSESSMENT_ADMIN_USERNAME", "").strip()
    password = os.environ.get("ASSESSMENT_ADMIN_PASSWORD", "").strip()
    if not username or not password:
        raise ValueError(
            "Set ASSESSMENT_ADMIN_USERNAME and ASSESSMENT_ADMIN_PASSWORD in .env"
        )
    return username, password


def _save_oauth_token(creds: UserCredentials) -> None:
    OAUTH_TOKEN_JSON.write_text(creds.to_json(), encoding="utf-8")


def _run_oauth_browser_flow() -> UserCredentials:
    import json

    from google_auth_oauthlib.flow import InstalledAppFlow

    if not OAUTH_CLIENT_JSON.is_file():
        raise ValueError(
            f"Missing {OAUTH_CLIENT_JSON.name}. "
            "Add OAuth client JSON from Google Cloud Console, then run setup_google_oauth.py"
        )
    with OAUTH_CLIENT_JSON.open(encoding="utf-8") as f:
        client_config = json.load(f)
    flow = InstalledAppFlow.from_client_config(client_config, SHEETS_SCOPES)
    flow.redirect_uri = f"http://localhost:{OAUTH_PORT}/"
    print(
        f"\n[Google] Opening browser to sign in (http://localhost:{OAUTH_PORT}/) ...\n",
        flush=True,
    )
    return flow.run_local_server(
        port=OAUTH_PORT,
        open_browser=True,
        prompt="consent",
        access_type="offline",
    )


def _creds_from_env() -> UserCredentials | None:
    client_id = os.environ.get("GOOGLE_OAUTH_CLIENT_ID", "").strip()
    client_secret = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET", "").strip()
    refresh_token = os.environ.get("GOOGLE_OAUTH_REFRESH_TOKEN", "").strip()
    if not all((client_id, client_secret, refresh_token)):
        return None
    return UserCredentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=SHEETS_SCOPES,
    )


def get_sheets_service():
    """Sheets API client — uses google-oauth-token.json if present, else .env refresh token."""
    creds: UserCredentials | None = None
    if OAUTH_TOKEN_JSON.is_file():
        creds = UserCredentials.from_authorized_user_file(str(OAUTH_TOKEN_JSON), SHEETS_SCOPES)
    if creds is None:
        creds = _creds_from_env()
    if creds is None:
        raise ValueError(
            "Google Sheets sign-in required. Run once: python setup_google_oauth.py "
            "(needs oauth-client.json in this folder)."
        )

    if not creds.valid:
        try:
            creds.refresh(Request())
            _save_oauth_token(creds)
        except RefreshError:
            auto = os.environ.get("GOOGLE_AUTO_OAUTH_RELOGIN", "true").lower() not in (
                "0",
                "false",
                "no",
            )
            if auto and OAUTH_CLIENT_JSON.is_file():
                creds = _run_oauth_browser_flow()
                _save_oauth_token(creds)
            else:
                raise ValueError(
                    "Google sign-in expired. Run: python setup_google_oauth.py"
                ) from None

    return build("sheets", "v4", credentials=creds)


def _extract_spreadsheet_id(sheet_url: str) -> str:
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", sheet_url.strip())
    if not match:
        raise ValueError(f"Could not parse spreadsheet id from URL: {sheet_url}")
    return match.group(1)


def _col_letter(col: int) -> str:
    """1-indexed column number → A1 column letters."""
    result = ""
    while col > 0:
        col, rem = divmod(col - 1, 26)
        result = chr(65 + rem) + result
    return result


def _normalize_header(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().lower())


def _find_header_columns(headers: list[str]) -> tuple[int, int]:
    """
    Return 0-indexed (question_id_col, question_content_col).
    question_id defaults to column A when the header name is missing.
    """
    normalized = [_normalize_header(h) for h in headers]

    id_col = 0
    for idx, name in enumerate(normalized):
        if name in QUESTION_ID_HEADERS:
            id_col = idx
            break

    content_col = None
    for idx, name in enumerate(normalized):
        if name in QUESTION_CONTENT_HEADERS:
            content_col = idx
            break

    if content_col is None:
        raise ValueError(
            "Could not find a 'question_content' column in row 1. "
            f"Headers found: {headers}"
        )
    return id_col, content_col


def read_sheet_rows(sheet_url: str, sheet_name: str) -> tuple[str, int, int, list[tuple[int, str]]]:
    """
    Read question IDs from the sheet.

    Returns:
      spreadsheet_id, question_id_col (0-idx), question_content_col (0-idx),
      list of (row_number_1_indexed, question_id)
    """
    spreadsheet_id = _extract_spreadsheet_id(sheet_url)
    sheets = get_sheets_service()
    result = (
        sheets.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range=f"'{sheet_name}'")
        .execute()
    )
    values = result.get("values", [])
    if not values:
        raise ValueError(f"Sheet '{sheet_name}' is empty")

    headers = values[0]
    id_col, content_col = _find_header_columns(headers)

    rows: list[tuple[int, str]] = []
    for row_idx, row in enumerate(values[1:], start=2):
        if id_col >= len(row):
            continue
        qid = str(row[id_col]).strip()
        if not qid:
            continue
        rows.append((row_idx, qid))

    if not rows:
        raise ValueError(f"No question_id values found in column {_col_letter(id_col + 1)}")

    return spreadsheet_id, id_col, content_col, rows


def update_question_contents(
    spreadsheet_id: str,
    sheet_name: str,
    content_col: int,
    updates: list[tuple[int, str]],
) -> None:
    """Batch-write question_content values. updates = [(row_1_indexed, content), ...]."""
    if not updates:
        return

    sheets = get_sheets_service()
    data = [
        {
            "range": f"'{sheet_name}'!{_col_letter(content_col + 1)}{row}",
            "values": [[content]],
        }
        for row, content in updates
    ]
    sheets.spreadsheets().values().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"valueInputOption": "RAW", "data": data},
    ).execute()


def _build_driver() -> webdriver.Chrome:
    headless = os.environ.get("ASSESSMENT_HEADLESS", "false").lower() in (
        "1",
        "true",
        "yes",
    )
    options = webdriver.ChromeOptions()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    chrome_bin = os.environ.get("CHROME_BIN") or os.environ.get("GOOGLE_CHROME_BIN")
    if chrome_bin:
        options.binary_location = chrome_bin
    return webdriver.Chrome(options=options)


def _login(driver: webdriver.Chrome, wait: WebDriverWait, username: str, password: str) -> None:
    driver.get(LOGIN_URL)
    user_field = wait.until(EC.presence_of_element_located((By.ID, "id_username")))
    user_field.clear()
    user_field.send_keys(username)
    pass_field = driver.find_element(By.ID, "id_password")
    pass_field.clear()
    pass_field.send_keys(password)
    driver.find_element(By.CSS_SELECTOR, "div.submit-row input[type='submit']").click()
    wait.until(EC.presence_of_element_located((By.ID, "user-tools")))


def _extract_one_question(driver: webdriver.Chrome, wait: WebDriverWait, question_id: str) -> str:
    driver.get(QUESTION_LIST_URL)
    search = wait.until(EC.presence_of_element_located((By.ID, "searchbar")))
    search.clear()
    search.send_keys(question_id)
    driver.find_element(By.CSS_SELECTOR, "input[type='submit'][value='Search']").click()

    link = wait.until(
        EC.element_to_be_clickable(
            (By.CSS_SELECTOR, f"th.field-id a[href*='{question_id}']")
        )
    )
    link.click()

    content_el = wait.until(EC.presence_of_element_located((By.ID, "id_content")))
    # Prefer value attribute — matches the textarea body in Django admin
    content = content_el.get_attribute("value")
    if content is None:
        content = content_el.text
    return (content or "").strip()


def extract_and_update(sheet_url: str, sheet_name: str, skip_existing: bool = False) -> dict:
    spreadsheet_id, _id_col, content_col, rows = read_sheet_rows(sheet_url, sheet_name)
    username, password = _admin_creds()

    # Optionally skip rows that already have question_content
    if skip_existing:
        sheets = get_sheets_service()
        existing = (
            sheets.spreadsheets()
            .values()
            .get(
                spreadsheetId=spreadsheet_id,
                range=f"'{sheet_name}'!{_col_letter(content_col + 1)}2:{_col_letter(content_col + 1)}",
            )
            .execute()
            .get("values", [])
        )
        existing_by_row = {
            idx + 2: (cell[0].strip() if cell else "")
            for idx, cell in enumerate(existing)
        }
        rows = [(r, q) for r, q in rows if not existing_by_row.get(r)]

    if not rows:
        return {
            "status": "ok",
            "message": "Nothing to update (all rows already have question_content or no IDs)",
            "updated": 0,
            "failed": 0,
        }

    driver = _build_driver()
    wait = WebDriverWait(driver, WAIT_TIME)
    sheet_updates: list[tuple[int, str]] = []
    failures: list[dict] = []

    try:
        _login(driver, wait, username, password)
        for row_num, question_id in rows:
            try:
                print(f"[row {row_num}] Extracting {question_id} ...", flush=True)
                content = _extract_one_question(driver, wait, question_id)
                if not content:
                    raise ValueError("Empty content in #id_content")
                sheet_updates.append((row_num, content))
                print(f"[row {row_num}] OK ({len(content)} chars)", flush=True)
                time.sleep(0.3)
            except (TimeoutException, WebDriverException, ValueError) as exc:
                failures.append({"row": row_num, "question_id": question_id, "error": str(exc)})
                print(f"[row {row_num}] FAILED: {exc}", flush=True)

        if sheet_updates:
            # Write in chunks to avoid huge payloads
            chunk_size = 50
            for i in range(0, len(sheet_updates), chunk_size):
                update_question_contents(
                    spreadsheet_id, sheet_name, content_col, sheet_updates[i : i + chunk_size]
                )
            print(f"Updated {len(sheet_updates)} row(s) in '{sheet_name}'.", flush=True)
    finally:
        try:
            driver.quit()
        except WebDriverException:
            pass

    return {
        "status": "ok" if not failures else "partial",
        "updated": len(sheet_updates),
        "failed": len(failures),
        "failures": failures,
        "spreadsheet_id": spreadsheet_id,
        "sheet_name": sheet_name,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract Django-admin question content into a Google Sheet column."
    )
    parser.add_argument("--sheet-url", help="Google Sheet URL")
    parser.add_argument("--sheet-name", help="Sub-sheet / tab name")
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip rows that already have question_content filled",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    sheet_url = (args.sheet_url or input("Sheet URL: ").strip()).strip()
    sheet_name = (args.sheet_name or input("Sub sheet name: ").strip()).strip()
    if not sheet_url or not sheet_name:
        raise SystemExit("sheet URL and sub sheet name are required")

    result = extract_and_update(sheet_url, sheet_name, skip_existing=args.skip_existing)
    print(result)
    if result.get("failed"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
