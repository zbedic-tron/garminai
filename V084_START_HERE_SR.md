# GarminAI Public v0.8.4 — Neon Google Sign-In POC (samo staging)

Ovo je **eksperimentalni** prvi browser-to-Neon Google login test, ne završena produkciona autentifikacija. Sav MCP rad i dalje je `DEMO_ONLY`.

**1.** Prenesi sadržaj `public/` iz ZIP-a u postojeći `public/` na GitHub-u. `render.yaml` ostaje u korenu repozitorijuma. Proveri `/healthz` = `0.8.4` i prethodne `GARMINAI_DB_CHECK` i `GARMINAI_NEON_AUTH_CHECK` logove.

**2.** Na Render → Environment dodaj `NEON_AUTH_STAGING_URL` sa *auth-staging* grane Neona; ne menjaj `DATABASE_URL` ili produkcioni `NEON_AUTH_URL`.

**3.** Samo tokom testa postavi `GARMINAI_STAGING_LOGIN_ENABLED=1` i otvori `/auth/staging/google`. To je eksperiment koji možda neće proći zbog CORS/third-party cookies. Ne unosi tajne u chat ili GitHub.

**4.** Posle testa vrati `GARMINAI_STAGING_LOGIN_ENABLED=0`.

Detaljnije i ograničenja: `public/docs/V084_AUTH_STAGING_POC_SR.md`.
