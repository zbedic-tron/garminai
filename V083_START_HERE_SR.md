# GarminAI Public v0.8.3 — Neon Auth connection staging

Sadržaj `public/` prekopiraj u postojeći `public/` repozitorijuma. `render.yaml` ostaje u root-u.

Posle Render deploya: `/healthz` treba da pokaže `0.8.3`.

Onda u Render Environment dodaj `NEON_AUTH_URL`: kopira se iz Neon Settings → Better Auth → **Auth URL** (javni URL, bez lozinke). Sačuvaj i proveri `GARMINAI_NEON_AUTH_CHECK` u Render Logs.

Za sada **ne uključuj Neon OAuth Provider**: login i consent još ne autentifikuju korisnike. Ne unositi Garmin ključeve.

Detalji: `public/docs/V083_NEON_AUTH_CONNECTION_SR.md`.
