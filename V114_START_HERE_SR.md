# GarminAI Public v1.1.4 — GITHUB/RENDER UPUTSTVO

## 1. Instalacija (diferencijalni ZIP)
Ova arhiva sadrži samo nove i izmenjene fajlove u odnosu na v1.1.3. Raspakuj i prekopiraj njihove relativne putanje u GitHub repozitorijum. **Ne briši ostale postojeće fajlove**. Na GitHub-u uradi Commit changes; Render će zatim primeniti novu verziju.

## 2. Provera
- `/healthz` => `version: 1.1.4`.
- `https://garminai-public-demo.onrender.com/garmin/ingress/readiness` => `readiness: BLOCKED`, `live_garmin_push_enabled: false`.
- `/garmin/integration/status` => `push_ingestion_enabled:false`, `mcp_real_garmin_data_enabled:false`.
- Po uspešnom v1.1.3 sintetičkom testu ostavi `GARMINAI_PUSH_REHEARSAL_STAGING_ENABLED=0`.

## 3. Šta NE raditi
- NE uključivati nijedan Garmin endpoint; NE uključivati direktan prijem kroz Render.
- NE dodavati pristupne ključeve u GitHub; NE menjati postojeći Garmin OAuth, Neon RLS, SQL migracije ili ChatGPT plugin.
- NE instalirati plaćene servise i ne praviti automatski keep-alive kao zamenu za pouzdan SLA.

## 4. Sutra
Ažuriran `public/docs/PROJECT_CONTINUITY_SR.md`. U novom ChatGPT razgovoru priloži taj dokument; uputstvo sadrži poslednje provere, ograničenja i naredni korak. Bez garancije da će se stanje automatski videti u drugom razgovoru bez dokumenta.

## 5. Bezbednost i povratak
Ova verzija dodaje samo read-only pregled i regresione testove. Svi Garmin push POST-ovi ostaju `503` u kodu. Povratak: primeni v1.1.3 izmenjene fajlove bez SQL rollback-a. Nema novih troškova ni promena infrastrukture.
