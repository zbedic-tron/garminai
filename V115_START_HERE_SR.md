# GarminAI Public v1.1.5 — UPUTSTVO ZA UPLOAD

**Nastavljamo od potvrđenog v1.1.4.** Ovo je diferencijalni ZIP, a ne kompletan repozitorijum.

1. Raspakuj ZIP lokalno. U postojećem GitHub repozitorijumu `zbedic-tron/garminai` prebaci sadržaj `public/` u isti postojeći `public/` direktorijum, zadržavajući strukturu foldera; ne briši ostale fajlove. Korenski `V115_START_HERE_SR.md` i `V115_MANIFEST.json` su samo uputstvo/metapodaci, ne moraju se uploadovati.
2. GitHub Commit → Render automatski deploy; ne menjaj Start Command.
3. Otvori `/healthz`; očekuj `version: 1.1.5`.
4. Otvori `/garmin/ingress/readiness` → `readiness: BLOCKED` i `live_garmin_push_enabled: false`.
5. Otvori **NOVU** `/garmin/ingress/edge-lab` → `mode: OFFLINE_SYNTHETIC_EDGE_LAB`, `edge_worker_deployed_by_garminai: false`.
6. Otvori `/garmin/integration/status` → `push_ingestion_enabled: false`, `mcp_real_garmin_data_enabled: false`.
7. Render Environment: `GARMINAI_PUSH_REHEARSAL_STAGING_ENABLED=0` (kako je već potvrđeno). Nema SQL migracija, novih tajni ili plaćenih servisa.
8. **Ništa ne uključuj u Garmin Endpoint Configuration.** Novi Cloudflare `edge_lab_v115/` nije automatski deployovan, nije potreban Cloudflare nalog i nije dozvoljen za stvarne Garmin poruke.

Lokalni test bez naloga:
`node --test public/edge_lab_v115/test_worker.mjs` (Node 20+).

**VAŽNO:** Trenutni Garmin OAuth link se proverava preko `get_garmin_connection_status`. `garmin_oauth: NOT_CONNECTED` u demo `/healthz` odnosi se na demo režim, ne na stvarno povezivanje.

**Projektni kontinuitet:** `public/docs/PROJECT_CONTINUITY_SR.md` ažuriran u ovom ZIP-u.

**Pravilo: 0 € dodatnih troškova; nijedan pravi Garmin podatak nije primljen ili podeljen.**
