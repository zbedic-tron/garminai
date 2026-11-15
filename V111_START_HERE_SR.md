# START HERE — GarminAI Public v1.1.1 (delta)

Mali diferencijalni ZIP u odnosu na već instalirani v1.1.0. `public/` iz paketa kopira se u postojeći GitHub `public/` bez brisanja drugih datoteka. Zatim Render redeploy, `/healthz` → `1.1.1` i `/garmin/integration/status` → `push_ingestion_enabled:false`.

U Neon SQL Editoru na **istoj grani koju koristi Render** izvršiti `public/sql/005_garmin_push_inbox_offline.sql`. Posle migracije proveriti RLS i privilegije prema `public/docs/V111_GARMIN_PUSH_INGRESS_OFFLINE_SR.md`.

**Nema Garmin API Tools podešavanja, novih Render env promenljivih, promene Garmin OAuth ključeva, osvežavanja ChatGPT MCP alata ili plaćenih servisa.**

Javni Garmin push ostaje `503`. Nova inbox tabela služi samo za simulirane događaje i offline testove. Poverljiva Garmin dokumentacija se **ne uključuje** u ZIP, niti su partnerovi IP opsezi objavljeni u kodu.

Za proveru: `cd public && python -m unittest discover -s tests -q` i Node testovi iz prethodne verzije (bez korisničkih podataka). Ako postoji problem, rollback iz uputstva; ne briši SQL tabelu koja potencijalno ima podatke. Politika: **0 €**.
