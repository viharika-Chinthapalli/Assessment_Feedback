"""One-time Google sign-in for Sheets access. Saves google-oauth-token.json."""

import json
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

BASE_DIR = Path(__file__).resolve().parent
OAUTH_CLIENT_JSON = BASE_DIR / "oauth-client.json"
OAUTH_TOKEN_JSON = BASE_DIR / "google-oauth-token.json"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
PORT = 8080


def main() -> None:
    if not OAUTH_CLIENT_JSON.is_file():
        raise SystemExit(
            f"Missing {OAUTH_CLIENT_JSON.name}. "
            "Download OAuth client JSON from Google Cloud Console (Desktop or Web app)."
        )
    with OAUTH_CLIENT_JSON.open(encoding="utf-8") as f:
        client_config = json.load(f)

    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    flow.redirect_uri = f"http://localhost:{PORT}/"
    print(f"\nOpening browser for Google sign-in (http://localhost:{PORT}/) ...\n")
    creds = flow.run_local_server(port=PORT, open_browser=True, prompt="consent", access_type="offline")
    OAUTH_TOKEN_JSON.write_text(creds.to_json(), encoding="utf-8")
    print(f"Saved: {OAUTH_TOKEN_JSON}\nYou can run extract_question_content.py now.\n")


if __name__ == "__main__":
    main()
