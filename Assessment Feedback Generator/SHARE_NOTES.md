# Assessment Feedback Generator — Share / Handoff Notes

## Full setup process (first time)

### 1. Get the code
Open the `Assessment Feedback Generator` folder in a terminal:

```powershell
cd "Assessment Feedback Generator"
```

### 2. Install Python packages
Use Python 3.10+ (3.11/3.12/3.14 also fine).

```powershell
pip install -r requirements.txt
```

Packages installed: `python-dotenv`, `openai`, Google API client/auth libs, `python-docx`, etc.

### 3. Create `.env`
Copy the example file:

```powershell
copy .env.example .env
```

Edit `.env` and fill values:

```env
# --- Free LLM (pick one) ---
LLM_PROVIDER=groq
GROQ_API_KEY=gsk_your_key_here

# Optional alternative:
# LLM_PROVIDER=gemini
# GEMINI_API_KEY=your_gemini_key_here

OPENAI_MAX_TOKENS=4000
GOOGLE_AUTO_OAUTH_RELOGIN=true

# Optional cutoffs (leave blank until finalized)
# CUTOFF_DSA=
# CUTOFF_SQL=
# CUTOFF_CS=
# CUTOFF_OVERALL=
```

**How to get a free LLM key**
- Groq (default): https://console.groq.com/keys → put in `GROQ_API_KEY`
- Gemini: https://aistudio.google.com/apikey → set `LLM_PROVIDER=gemini` and `GEMINI_API_KEY`

Optional Groq model override in `.env`:
```env
OPENAI_MODEL=openai/gpt-oss-120b
```

### 4. Google OAuth files
These live in the same folder as `main.py`:

| File | Purpose |
|------|---------|
| `oauth-client.json` | Google Cloud OAuth client credentials (required before first login) |
| `google-oauth-token.json` | Created automatically after you sign in once |

**If `oauth-client.json` is missing**, create one from Google Cloud Console:
1. Open https://console.cloud.google.com/
2. Select / create a project
3. Enable APIs:
   - **Google Sheets API**
   - **Google Drive API**
4. Go to **APIs & Services → Credentials → Create credentials → OAuth client ID**
5. Application type: **Web application** (or Desktop)
6. Add authorized redirect URI: `http://localhost:8080/`
7. Download the JSON and save it as:
   `Assessment Feedback Generator/oauth-client.json`

Example shape (your IDs will differ):

```json
{
  "web": {
    "client_id": "...apps.googleusercontent.com",
    "project_id": "...",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "client_secret": "..."
  }
}
```

### 5. One-time Google sign-in
```powershell
python setup_google_oauth.py
```
- Browser opens → sign in with the Google account that can **edit** the spreadsheet
- This creates `google-oauth-token.json` in the folder
- If the token expires later, running `main.py` can re-open login when `GOOGLE_AUTO_OAUTH_RELOGIN=true`

### 6. Share the spreadsheet
Share the source Google Sheet with the **same Google account** used in OAuth (Editor access).

### 7. Run
```powershell
python main.py
```
Enter:
1. Sheet URL  
2. Sub sheet / tab name  

Or non-interactive:
```powershell
python main.py --sheet-url "https://docs.google.com/spreadsheets/d/..../edit" --sheet-name "YourTabName"
```

Test with 1–2 students first:
```powershell
python main.py --sheet-url "..." --sheet-name "YourTabName" --limit 2
```

Sheet only (skip Google Docs):
```powershell
python main.py --skip-docs
```

---

## What gets created
- New tab: `Feedback_<source_tab>` (or `Feedback_<source_tab> (2)` if name already exists)
- Per student: styled **Google Doc** + row in the feedback tab
- Look at **column Z (`google_doc_url`)** for the Doc link

---

## Do not share / do not commit
These contain secrets (already in `.gitignore`):
- `.env`
- `oauth-client.json`
- `google-oauth-token.json`

Each teammate should create their own `.env` and run `setup_google_oauth.py` once.

---

## Quick checklist
- [ ] Python installed
- [ ] `pip install -r requirements.txt`
- [ ] `.env` created from `.env.example` with `GROQ_API_KEY` (or Gemini)
- [ ] `oauth-client.json` present
- [ ] Sheets API + Drive API enabled on the Google Cloud project
- [ ] `python setup_google_oauth.py` completed
- [ ] Spreadsheet shared with that Google account (Editor)
- [ ] `python main.py` with sheet URL + sub sheet name
