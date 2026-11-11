# GarminAI Public v0.1 — DEMO MCP + literature

**STATUS: LOCAL DEMONSTRATION ONLY. NOT A PUBLIC GARMIN INTEGRATION.**

This is **separate** from the GarminAI Windows application and its private SQLite database, tokens, settings, and scheduled jobs. Never upload the Windows app's credentials or real athlete archives here.

## Features

- MCP tools: `get_sync_status`, `get_activities`, `get_activity_details`, `get_training_summary`, `search_training_literature`, `get_distance_guidance`.
- All activity data is **fictional** and tagged `DEMO_ONLY`.
- Human-reviewed bibliography (5 initial references) with source URLs.
- Optional Crossref candidate lookup: discovers metadata; **does not approve or import automatically**.
- English/Serbian conversational policy in `docs/CHATGPT_INSTRUCTIONS.md`.

## Windows / PowerShell local test (Python 3.11–3.14 recommended)

```powershell
cd public
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m garminai_public.server
```

If Python 3.13 is unavailable, replace `py -3.13` with another compatible Python. MCP v1 is pinned for a reproducible prototype; review upgrades before release.

Demo MCP endpoint: `http://127.0.0.1:8000/mcp` (the SDK's default). This **local** endpoint is not accessible from ChatGPT without a supported secure tunnel/remote deployment. Do not expose it publicly yet, because v0.1 has **no authentication**.

Run literature tests without MCP installed:

```powershell
python -m unittest discover -s tests -v
```

## Expand bibliography (optional)

```powershell
python -m garminai_public.literature_admin --query "marathon endurance training systematic review"
```

This contacts Crossref only when manually invoked; adds *candidates*, not approved evidence. Human editor verifies full research claims, quality and limitations before adding to `data/literature/approved.json`. No paper text is copied automatically.

## Next milestones (NOT IMPLEMENTED)

1. Garmin official Business OAuth approval and integration, including consent and permissions.
2. User-authenticated MCP server; isolated multi-user storage and token encryption.
3. Data deletion, privacy retention, breach response and production hosting.
4. Background Garmin sync/webhook support **subject to official API permissions**.
5. Safety, load testing, testing with voluntary TRON pilot participants, public review.

Public GitHub Pages website and repo should continue functioning. Upload the **`public/` folder** alongside existing website files, not instead of them.
