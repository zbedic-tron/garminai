# GarminAI Public v1.1.6 — SYNTHETIC CLOUDFLARE EDGE DEPLOYMENT LAB

## GitHub + Render (bezbedno, bez Cloudflare naloga)
1. ZIP je DELTA u odnosu na već instaliran v1.1.5; raspakuj ga i samo izmenjene fajlove iz `public/` uploaduj na iste putanje GitHub repozitorijuma (ne briši ostale fajlove). Commit.
2. Render automatski deploy; proveri `https://garminai-public-demo.onrender.com/healthz` -> version 1.1.6.
3. `https://garminai-public-demo.onrender.com/garmin/ingress/readiness` -> `readiness: BLOCKED` (to je očekivano).
4. `https://garminai-public-demo.onrender.com/garmin/ingress/edge-lab` -> `mode: OPTIONAL_REMOTE_SYNTHETIC_EDGE_LAB`, `real_garmin_push_enabled` nije dozvoljen.
5. Nema nove Neon migracije, Render varijable, Garmin OAuth podešavanja ni novih MCP alata. Stvarni Garmin push ostaje isključen.

## Opciono: stvarni Cloudflare Workers Free / D1 sintetički test
- Potrebni su besplatan Cloudflare Workers Free nalog i Node.js 20+ na Windowsu; ništa se ne deployuje automatski GitHub commitom.
- Prati `public/edge_lab_v116/README_SR.md`. Skripta `Setup-Cloudflare-Free.ps1 -Deploy` kreira odvojenu D1 bazu, Worker i tajnu tek kada TI potvrdiš Free plan. Nema Garmin podataka.
- Pošalji SAMO sigurni JSON rezultat `first_http/repeat_http/conflict_http/...` i rezultat D1 COUNT upita; **ne šalji LAB_TOKEN, Garmin OAuth tokene, Cloudflare API token ili .env fajlove**.
- Ni po koju cenu ne unositi Cloudflare Worker URL u Garmin Endpoint Configuration; to nije validiran Garmin webhook.

0 € dodatnih troškova. Diferencijalno pakovanje <100 fajlova. Projektni dosije: `public/docs/PROJECT_CONTINUITY_SR.md`.
