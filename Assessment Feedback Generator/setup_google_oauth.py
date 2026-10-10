"""One-time Google sign-in for Sheets + Docs + Drive. Saves google-oauth-token.json."""

from google_auth import OAUTH_TOKEN_JSON, _save_oauth_token, run_oauth_browser_flow


def main() -> None:
    creds = run_oauth_browser_flow()
    _save_oauth_token(creds)
    print(f"\nSaved: {OAUTH_TOKEN_JSON}")
    print("Scopes: Sheets + Docs + Drive (file create)\n")


if __name__ == "__main__":
    main()
