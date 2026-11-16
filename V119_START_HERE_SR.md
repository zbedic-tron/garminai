# GarminAI Public v1.1.9 — START (SR)

**RELEASE:** Synthetic Delivery Reliability & Observability. Najpre pročitaj `public/docs/V119_RELIABILITY_OBSERVABILITY_SR.md`.

## Potrebno uraditi

1. Raspakuj ZIP. Na GitHub-u `zbedic-tron/garminai` prenesi nove/izmenjene fajlove iz `public/` na iste putanje; ne briši postojeće. Commit → sačekaj da Render deployment završi.
2. `https://garminai-public-demo.onrender.com/healthz` mora vratiti `version:1.1.9`.
3. `https://garminai-public-demo.onrender.com/garmin/ingress/delivery-observability` mora vratiti `mode:SYNTHETIC_RELIABILITY_READ_ONLY`, `operator_manual_retry_enabled:false`, `production_readiness:BLOCKED`.
4. ChatGPT GarminAI MCP → Settings → Manage app → Refresh tools. Ukupno 12 alata.
5. Pozovi samo **read-only** `get_synthetic_delivery_observability`. Pošto je v1.1.8 završio ACKED sa 3 claim-a, očekuje se `ACKED_SYNTHETIC`, `d1_claim_attempts=3`, `retry_permitted=false` ako stanje nije menjano.
6. **NE uključuj nove Render testne flag-ove** dok je događaj već ACKED. Novi flag `GARMINAI_EDGE_RELIABILITY_STAGING_ENABLED` po podrazumevanom stanju je 0 (ili nije postavljen). Nema potrebe pokretati mutacioni `run_synthetic_delivery_safe_retry` za ovaj već dovršeni događaj.

## Šta ne radiš

- **Ne pokreći** Cloudflare setup, niti pravi novu bazu, niti izvršavaj SQL migracije. Ne rotiraj postojeći LAB_TOKEN/BRIDGE_TOKEN.
- Ne uključuj Garmin push, stvarne aktivnosti u ChatGPT, plaćene servise ili novu Garmin autorizaciju.
- Ne menjaj lokalni `D:\Downloads\GarminAI-Public-v1.1.6\public\edge_lab_v116` — Cloudflare Worker v1.1.8 ostaje netaknut.

## Potvrđeni lokalni testovi pre distribucije

`pytest` i Node regresija moraju proći. Lokalni testovi nisu potvrda live Render instalacije. Korisnik treba da vrati zdravstveni i read-only MCP status.

## Načela

0 € dodatnih troškova, diferencijalni ZIP <100 fajlova, javni Garmin webhook 503, nema autopilota bez operator-odobrenja. `public/docs/PROJECT_CONTINUITY_SR.md` je kanonski handoff za sledeći thread.
