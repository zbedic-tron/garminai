# GarminAI Public v0.6 — Neon PostgreSQL (SR)

## Granice ove verzije

- Stvarni Garmin OAuth, push ingest, ChatGPT korisnicki login i AI obrada OSTAJU ISKLJUCENI.
- Javne MCP alatke i dalje prikazuju samo **izmisljene** treninge.
- v0.6 dodaje SQL semu sa RLS i Python repozitorijum za **buduce** proverene identitete.
- Nema automatskog citanja/snimanja stvarnih Garmin podataka, niti importovanja privatne Windows arhive.
- `GARMINAI_DEMO_TOKEN_SHA256` je samo operatorski kljuc za DEMO, **ne** identitet korisnika.

## Predlozeni redosled (bez povratnog rizika)

1. Postavi sadrzaj `public/` preko postojeceg `public/` na GitHub-u.
   `render.yaml` iz ZIP-a ide u **koren repozitorijuma**. Ne menjaj HTML sajta.
2. Render treba da deploy-uje verziju `0.6.0`. Proveri `/healthz` i
   `/integration/readiness`. Svi zivi Garmin tokovi ostaju iskljuceni.
3. **Nemoj jos dodavati DATABASE_URL** u Render dok ne kreiramo zasebnu
   rolu sa minimalnim pravima i proverimo SQL semu.
4. U Neon projektu `garminai-public`, na branch `production`, otvori SQL Editor.
   Pregledaj `public/sql/001_init.sql`; zatim ga primeni u SQL Editor-u.
   Skripta je ponovljiva za tabele i politike (ne brise podatke).
5. SQL Editor administrativna sesija treba da kreira odvojenu runtime ulogu
   `garminai_runtime` sa jakom nasumicnom lozinkom. Ne upisuj lozinku u GitHub.
   Naziv role moze biti drugaciji; nemoj koristiti `neondb_owner` u aplikaciji.
   Primer, nakon kreiranja role:

   GRANT USAGE ON SCHEMA garminai TO garminai_runtime;
   GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA garminai TO garminai_runtime;

   Runtime rola ne sme imati BYPASSRLS niti vlasnistvo nad tabelama.
6. Kreiraj poseban connection string za runtime rolu sa TLS i pooling
   (po mogucnosti sa sertifikatskom proverom). Unesi ga u Render kao
   `DATABASE_URL`, bez deljenja u razgovoru ili na GitHub-u.
7. Generisi zaseban `GARMINAI_TOKEN_ENCRYPTION_KEY` od **32 nasumicna bajta**
   kodirana kao URL-safe base64; unosi se samo u Render Environment.
   Primer sa instaliranim Pythonom:

   python -c "import secrets,base64;print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"

   Nemoj slati ili slikati tu vrednost. Bez zavrsenog realnog OAuth i provera
   nema potrebe da trenutno postavis ovaj kljuc.
8. Za sada testiranje vrsi pomocu `python -m pytest -q` iz `public/`.
   Ti testovi ne kontaktiraju Neon i ne koriste licne podatke.

## Napomena o RLS

Python `PostgresActivityStore` ne prima string korisnickog identiteta, vec
`VerifiedPrincipal`. U svakom DB transaction-u postavlja `garminai.subject`
parametar lokalno za tu transakciju, a SQL upiti dodatno filtriraju po subjektu.
RLS polise rade i kada aplikacioni kod omasi filter, ali to nije zamena za
proveru identiteta i kontrolu privilegija nad runtime DB rolom.

## Pre pustanja stvarnih korisnika

Mora se dovrsiti: ChatGPT/OAuth identitet (nezavisan od Garmin OAuth-a),
Garmin OAuth callback i server-side state, sigurno povezivanje Garmin user ID
sa identitetom ChatGPT korisnika, webhook/push potvrde i retry, validacija
Garmin payload-a, revokacija, brisanje, AI eksplicitna saglasnost, kontrole
pristupa, bezbednosna analiza i dokumentovani retention periodi.
Garmin Starter nema istorijski backfill; baza gradi istoriju od povezivanja.
Besplatni Neon i Render imaju resursne limite: 0 EUR nije garantovana
produkcijska usluga niti 24/7 pouzdan prijem push obavestenja.

Vazno: direktni Neon connection string iz `Connect` prozora cesto koristi
administrativnu rolu `neondb_owner`; NE KORISTI ga kao runtime `DATABASE_URL`.
