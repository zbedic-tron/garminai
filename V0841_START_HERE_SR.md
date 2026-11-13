# GarminAI Public v0.8.4.1 — Sign-in Diagnostics

U postojećem `public/` zameni fajlove iz ovog paketa, `render.yaml` stavi u koren. Bez novih SQL migracija i bez novih environment promenljivih.

Proveri `/healthz`: `0.8.4.1`, zatim probaj `/auth/staging/google`. Ako se pojavi greška, pošalji samo bezbedni **kod u uglastim zagradama**; nikad cookies, token ili OAuth URL.

Kada završiš, test flag `GARMINAI_STAGING_LOGIN_ENABLED` stavi na `0`.
