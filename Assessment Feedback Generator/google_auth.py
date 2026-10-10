"""Shared Google OAuth for Sheets + Docs + Drive."""

from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import load_dotenv
from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials as UserCredentials
from googleapiclient.discovery import build

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

OAUTH_TOKEN_JSON = BASE_DIR / "google-oauth-token.json"
OAUTH_CLIENT_JSON = BASE_DIR / "oauth-client.json"
OAUTH_PORT = int(os.environ.get("GOOGLE_OAUTH_PORT", "8080"))

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive.file",
]


def _save_oauth_token(creds: UserCredentials) -> None:
    OAUTH_TOKEN_JSON.write_text(creds.to_json(), encoding="utf-8")


def run_oauth_browser_flow() -> UserCredentials:
    from google_auth_oauthlib.flow import InstalledAppFlow

    if not OAUTH_CLIENT_JSON.is_file():
        raise ValueError(
            f"Missing {OAUTH_CLIENT_JSON.name}. Add OAuth client JSON, then run setup_google_oauth.py"
        )
    with OAUTH_CLIENT_JSON.open(encoding="utf-8") as f:
        client_config = json.load(f)
    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    flow.redirect_uri = f"http://localhost:{OAUTH_PORT}/"
    print(f"\n[Google] Opening browser sign-in (http://localhost:{OAUTH_PORT}/) ...\n", flush=True)
    return flow.run_local_server(
        port=OAUTH_PORT, open_browser=True, prompt="consent", access_type="offline"
    )


def get_credentials() -> UserCredentials:
    creds: UserCredentials | None = None
    if OAUTH_TOKEN_JSON.is_file():
        creds = UserCredentials.from_authorized_user_file(str(OAUTH_TOKEN_JSON), SCOPES)

    # Token missing Docs/Drive scopes from older Sheets-only login
    if creds is not None and creds.scopes:
        have = set(creds.scopes)
        need = set(SCOPES)
        if not need.issubset(have):
            print("[Google] Token missing Docs/Drive scopes — re-authorizing...", flush=True)
            creds = run_oauth_browser_flow()
            _save_oauth_token(creds)
            return creds

    if creds is None:
        if os.environ.get("GOOGLE_AUTO_OAUTH_RELOGIN", "true").lower() not in ("0", "false", "no"):
            creds = run_oauth_browser_flow()
            _save_oauth_token(creds)
            return creds
        raise ValueError("Google sign-in required. Run: python setup_google_oauth.py")

    if not creds.valid:
        try:
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
                _save_oauth_token(creds)
            else:
                raise RefreshError("invalid credentials")
        except RefreshError:
            auto = os.environ.get("GOOGLE_AUTO_OAUTH_RELOGIN", "true").lower() not in (
                "0",
                "false",
                "no",
            )
            if auto and OAUTH_CLIENT_JSON.is_file():
                creds = run_oauth_browser_flow()
                _save_oauth_token(creds)
            else:
                raise ValueError("Google sign-in expired. Run: python setup_google_oauth.py") from None
    return creds


def get_sheets_service():
    return build("sheets", "v4", credentials=get_credentials())


def get_docs_service():
    return build("docs", "v1", credentials=get_credentials())


def get_drive_service():
    return build("drive", "v3", credentials=get_credentials())
