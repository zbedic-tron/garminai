# GarminAI Public v0.8.7.4 — Neon Consent: public-client metadata fix

## Šta je popravljeno

Na stvarnom staging Consent ekranu `GET /oauth2/public-client` vraća HTTP 200,
uz odgovarajući `client_id` i `client_name`, ali `redirect_uris: []`.
U Neon Console je istovremeno registrovan callback URL
`https://garminai-public-demo.onrender.com/auth/oauth-test/callback`.
Prethodni frontend je tretirao prazan javni niz kao dokaz neuspešne
registracije i zaključavao Approve i Deny (`CLIENT_NOT_VERIFIED`).

Od sada **prazan niz** javnih URI metapodataka ne blokira Consent. Ako endpoint
vrati neprazan niz, i dalje mora sadržati tačan očekivani callback; neispravan
tip se odbija. Klijent ID se i dalje proverava, kao i potpuni lokalni staging
zahtev (callback, scope, resource, code/S256, PKCE, state, prompt), a konačnu
verifikaciju potpisanog zahteva i registrovane adrese vrši Neon na serveru.
Dugmad se aktiviraju tek nakon postojeće provere sesije i klijenta.

## Postavljanje — isti postupak kao ranije

1. Raspakuj ceo ZIP.
2. Kopiraj **sadržaj `public/`** preko postojećeg `public/` u GitHub
   repozitorijumu `zbedic-tron/garminai`, i potvrdi Commit changes.
3. Neka Render završi novi deployment. Nema promena na Neon klijentu,
   Render environment promenljivama, SQL migracijama, Garmin API-ju ili MCP-u.
4. Proveri `https://garminai-public-demo.onrender.com/healthz`:
   očekuje se `version: 0.8.7.4`.
5. Proveri `/auth/oauth-ui/status`: očekuje se
   `oauth_ui_staging_enabled: true`, `oauth_ui_config_errors: []`.
6. Otvori `https://garminai-public-demo.onrender.com/auth/oauth-test` i pokreni
   potpuno **nov** test. Ne otvaraj stari Consent URL sa starim potpisom.
7. Na Consent-u potvrdi da Approve i Deny nisu zaključani. Pri kliku Neon
   i dalje može vratiti 400/401 ako nešto drugo nije validno; u tom slučaju
   pošalji samo status i bezbedan kod greške, bez potpisanih parametara/tokena.

## Bezbednosne granice

- Ovo je *staging-only* test OAuth-a. Ni produkcioni MCP ni Garmin podaci nisu aktivirani.
- Ne uključuj `Skip consent`, ne menja se Client ID niti se preskaču serverske validacije.
- Kod frontend-a ne može sam da potvrdi kriptografski `sig`; to radi Neon.
- Zadržana je ispravka `OAUTH_SESSION_LOOP` iz v0.8.7.3.

## Testiranje

Dodat je browser regresioni test za stvarni Neon odgovor s praznim `redirect_uris`,
uz testove za neprazan pogrešan niz, neispravan tip i odsutno polje.
Lokalni rezultati su navedeni u isporučenoj poruci (ne predstavljaju proveru
stvarnog Neon OAuth E2E toka).
