# GarminAI Public v0.5 — OAuth PKCE staging

Garmin-approved Activity API integration preparation, **no live Garmin connection yet**.

See `docs/V05_GARMIN_OAUTH_SR.md` for Serbian instructions and security requirements.

# GarminAI Public v0.4 — DEMO MCP + evidence library + identity isolation tests

A public **demo-only** MCP server with six tools and reviewed training literature.
The public server has no real users or Garmin integration.

- `/healthz` → version `0.4.0`, mode `DEMO_ONLY`.
- `/mcp` → static operator bearer gate from v0.3; NOT user OAuth.
- `garminai_public/identity.py` → local-only verified test principals.
- `garminai_public/tenant_db.py` → local-only tenant-isolated SQLite test store.
- Approved literature remains under `data/literature/approved.json`, with manual-review policy.

**Never upload Garmin credentials or private Windows application data.**
**Do not connect real athlete data to this server.**

Testing: `python -m pip install -r requirements.txt pytest` then `python -m pytest -q` from `public/`.
Deployment: root `render.yaml` points at `public/`. Set `GARMINAI_DEMO_TOKEN_SHA256` only in Render Environment.
See `docs/V04_SECURITY_SR.md` for boundaries and next implementation steps.
