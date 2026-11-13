# GarminAI Public v0.8.2 — Prvi korak: postavljanje staging stranica

**Ne uključuj još OAuth Provider u Neon-u.** Ovo su javne stranice za prikaz i bezbednosno testiranje, a ne funkcionalna korisnička autentifikacija.

1. Raspakuj ZIP; prenesi **sadržaj** `public/` u postojeći GitHub `public/`. Ne pravi `public/public/`.
2. `render.yaml` ostaje u glavnom direktorijumu GitHub repozitorijuma. Commit, Render auto-deploy.
3. Proveri `/healthz` (`0.8.2`) i Render Logs (`GARMINAI_DB_CHECK: PASS (OK)`).
4. Otvori `/auth/login` i `/auth/consent` — obe prikazuju *not active yet*.
5. Proveri `/auth/development-status`: `mcp_oauth_enabled:false`, `consent_submission_enabled:false`.

Nema novih SQL migracija, promenljivih okruženja ni plaćenih komponenti. Privatni GarminAI Windows netaknut.

Za detalje: `public/docs/V082_LOGIN_CONSENT_STAGING_SR.md`.
