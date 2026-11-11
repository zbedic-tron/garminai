# GarminAI Public v0.3 — DEMO MCP (zaštićen razvojni pristup)

**DEMO ONLY. Bez stvarnih Garmin podataka. NIJE spremno za javne korisnike.**

- Python MCP server, Render Streamable HTTP `/mcp`, `/healthz`.
- `GARMINAI_DEMO_TOKEN_SHA256` environment variable obavezan za MCP; bez njega 503, bez validnog Bearer tokena 401.
- Token je samo zajednička razvojna lozinka, ne korisnička autentifikacija ili Garmin OAuth.
- Šest demo MCP alatki, rangirana ručno odobrena literatura, predlozi novih radova sa obaveznom proverom.
- Primer izolacije po identitetu u `tenant_store.py` nije povezan sa javnim serverom i ne čuva stvarne aktivnosti.
- Pokrenuti testove: `pip install -r requirements.txt pytest` pa `pytest -q` iz `public/`.

**Uputstva:** `docs/DEPLOY_V03_SR.md`, `docs/SECURITY_AND_OAUTH_SR.md`, `docs/LITERATURE_V03_SR.md`.

Nikad ne postavljati privatni GarminAI Windows, lične FIT/JSON arhive ili tajne na ovaj repozitorijum.
