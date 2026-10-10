# Assessment Feedback Generator

Generates personalized student assessment feedback into a **new Google Sheet tab**. The source tab is never modified.

## Input
- Google Sheet URL
- Source subsheet name (e.g. `Viharika_working`)

## Output
- **One Google Doc per student** (sample-style feedback report)
- New index tab (default `Feedback_<source>`) with scores + `google_doc_url` (source tab untouched)

## Setup
```powershell
cd "Assessment Feedback Generator"
pip install -r requirements.txt
python setup_google_oauth.py
```

### Free LLM (recommended for now)
1. Create a free Groq key: https://console.groq.com/keys  
2. In `.env`:
   ```
   LLM_PROVIDER=groq
   GROQ_API_KEY=gsk_...
   ```
Or use Gemini free: `LLM_PROVIDER=gemini` + `GEMINI_API_KEY` from https://aistudio.google.com/apikey

Optional cutoffs (leave blank until finalized):
```
CUTOFF_DSA=
CUTOFF_SQL=
CUTOFF_CS=
CUTOFF_OVERALL=
```

## Run
```powershell
python main.py --sheet-url "YOUR_URL" --sheet-name "Viharika_working"
```

Test with a few students:
```powershell
python main.py --sheet-url "YOUR_URL" --sheet-name "Viharika_working" --limit 2
```

## Architecture
| Module | Role |
|--------|------|
| `sheets_client.py` | Google Sheets I/O (replace later with DB) |
| `processor.py` | Group by student/section, section scores once, validation |
| `analyzer.py` | Coding + MCQ evidence analysis (LLM) |
| `feedback_builder.py` | Sample-style feedback document |
| `config.py` | Sections, max marks, cutoffs |
| `main.py` | CLI orchestration |
