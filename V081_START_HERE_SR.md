# GarminAI Public v0.8.1 — Staging OAuth compatibility

1. Raspakuj ZIP. U GitHub repozitorijumu `zbedic-tron/garminai` prebaci **sadržaj** foldera `public/` u postojeći `public/` (ne `public/public/`). Zameni fajlove. `render.yaml` iz ZIP-a ostaje u korenu repozitorijuma.
2. Commit, Render automatic deploy.
3. Proveri `/healthz` => `0.8.1`; Render Logs => `GARMINAI_DB_CHECK: PASS (OK)`.
4. Otvori `/auth/development-status`; očekuje se `mcp_oauth_enabled:false`, `garmin_oauth_enabled:false`.
5. **NE** dodaj Garmin Client Secret, OAuth ključeve, korisničke naloge ili tabele. Nema novih SQL migracija. Ovo je samo staging validacija kompatibilnosti IdP-a.

Sajt GitHub Pages ostaje netaknut, kao i privatni GarminAI Windows.
