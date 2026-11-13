## GarminAI Public v0.8.3 — Neon Auth Connectivity Staging (2026-11-13)

- Render MCP stays `DEMO_ONLY` with six fictional-data tools. Live Garmin OAuth and MCP OAuth **are not enabled**.
- Added `NEON_AUTH_URL` operator configuration and read-only Neon Auth reachability check on startup (`GARMINAI_NEON_AUTH_CHECK`).
- `/auth/development-status` reports only nonsensitive readiness booleans. Login/consent pages are deliberately noninteractive until verified session and signed consent flow are implemented.
- See [V083_NEON_AUTH_CONNECTION_SR.md](docs/V083_NEON_AUTH_CONNECTION_SR.md).

# GarminAI Public v0.7 — PostgreSQL / User Isolation Staging

**DEMO ONLY:** Garmin OAuth login, actual Garmin Activity API push intake, ChatGPT
per-user authentication and AI analysis with real data are **NOT enabled**.

- `garminai_public/postgres_store.py`: verified-principal PostgreSQL query layer.
- `sql/001_init.sql`: PostgreSQL row-level security schema and consent tables.
- `garminai_public/token_vault.py`: AES-256-GCM encryption primitives, with identity binding.
- `garminai_public/db_readiness.py`: credential-safe configuration readout.
- Six fictional-data MCP tools and scientific source library unchanged.

**Important:** Database migration and real database integration have **not** been tested
against the user's Neon instance. Unit tests use fake connections and validate SQL
contracts; no private data is accessed.

**READ FIRST:** `docs/V06_POSTGRES_NEON_SR.md`.

Install dependencies and test: `python -m pip install -r requirements.txt pytest`
then `python -m pytest -q` from `public/`.

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


**v0.7:** Staged OAuth pending-attempt persistence (`garminai_public/oauth_pending.py`) and optional Neon migration `sql/002_oauth_pending.sql`. No live Garmin credentials or user authentication. See `docs/V07_OAUTH_STAGING_SR.md`.

### v0.7.1 — OAuth identity-binding staging

`garminai_public.oauth_binding.IdentityBoundGarminFlow` adds a verified-user
boundary around the already durable, single-use OAuth `state` and PKCE
verifier. It is deliberately **not wired to a public endpoint**. The Garmin
callback still returns 503 until a production-grade identity provider and
user session, encrypted token persistence, and consent management exist.
No changes to Garmin account credentials or private Windows GarminAI.

## v0.8.0 (MCP identity verification — staging)

Added offline RS256 JWT verification contract and tests. **Not wired into `/mcp`**;
existing development bearer gate and fictional activities remain unchanged.
See `docs/V08_MCP_IDENTITY_SR.md`.
