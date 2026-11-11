# GarminAI Public v0.2 — DEMO HTTPS MCP + literatura

**NOT PRODUCTION. Fictional data only. No Garmin connection, no user authentication, no real athlete data.**

This remains independent of GarminAI Windows; do not copy any Windows files, private tokens or athlete exports here.

## Included

- Six existing read-only MCP tools from v0.1 (`garminai_public/server.py`).
- New ASGI deployment in `garminai_public/http_server.py`, with `/healthz`, `/`, and `/mcp`.
- Render blueprint at repository root (`render.yaml`) and Serbian deployment guide `docs/RENDER_DEPLOY_SR.md`.
- Domain-specific Host/Origin allowlisting using Render's `RENDER_EXTERNAL_HOSTNAME`.
- Five manually approved research references in `data/literature/approved.json`; optional Crossref candidate metadata workflow (manual review required).

## Local checks

From `public/`:

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
uvicorn garminai_public.http_server:app --host 127.0.0.1 --port 8000
```

Visit http://127.0.0.1:8000/healthz. Remote URL after Render deploy: `https://YOUR-RENDER-HOST.onrender.com/mcp`.

## Critical guardrail

The public demo is *intentionally not authenticated*. All tools must continue to return **only fictional activities and public bibliography**. Adding real Garmin data requires a separate approved OAuth, authenticated MCP, user-level authorization checks, secure storage and a privacy/security review. Render Free is only for testing.
