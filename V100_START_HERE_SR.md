# GarminAI Public v1.0.0 — Garmin Activity API priprema (bezbedni staging)

**Polazna tačka: kompletni GarminAI Public v0.9.2 ZIP, bez novih servisa i bez dodatnih troškova.**

## Šta je stvarno novo

1. `garminai_public/garmin_activity_staging.py`: strogo ograničena lokalna provera JSON primerâ `activities` push obaveštenja (maks. 512 KiB, 100 aktivnosti, jedinstveni JSON ključevi, validacija osnovnih polja). Izbacuje `userAccessToken` i sva nepoznata polja. **Samo simulator/fixture, ne javni prijem.**
2. `TrustedOwnerBinding`: projektuje aktivnosti samo ako je već utvrđen validan interni `VerifiedPrincipal` i odgovarajući prethodno povezani Garmin `userId` iz pouzdanog skladišta. Odbija celu mešovitu poruku i konfliktnu duplu aktivnost; duplikate sa istim podacima prepoznaje. **Ne predstavlja stvarnu, već testnu Garmin nalog-vezu.**
3. Bezbedan status `/garmin/integration/status`, bez izlaganja Client ID/Secret, tokena, korisničkih ID-jeva ili sadržaja treninga.
4. Odvojene unapred imenovane Garmin push rute (`/garmin/push/activities`, `/garmin/push/activity-details`, `/garmin/push/activity-files`, `/garmin/push/manually-updated`, `/garmin/push/moveiq`, `/garmin/push/deregistrations`, `/garmin/push/permissions-change`) **uvek odgovaraju HTTP 503, čak i ako neko ručno postavi novu env promenljivu**. Ne obrađuju, ne potvrđuju i ne skladište podatke. To je namerna zaštita dok ne bude potvrđen Garminov mehanizam autentičnosti poziva, payload ugovor i sigurno upisivanje.
5. Garmin `/garmin/oauth/callback` i dalje namerno vraća 503: još ne postoji siguran live tok korisničke veze + rotacije šifrovanih tokena + revokacije. Postojeći Neon OAuth za ChatGPT radi nezavisno od Garmin OAuth-a.
6. Regresioni testovi za korisničku izolaciju, duplikate, maliciozni JSON, neodobrene tipove događaja, granice i fail-closed rutiranje.

## Šta OVA verzija NE obećava

**Nema stvarnog Garmin OAuth login-a ni čitanja stvarnih aktivnosti. Nije isporučen funkcionalan Garmin webhook prijemnik.** Ne unosi ove URL-ove u Garmin Endpoint Configuration, ne uključuj `enabled` niti pokreći Data Generator prema njima. Garmin bi u ovoj fazi dobijao 503. Ne menjati postojeće vrednosti Render secrets niti slati njihove vrednosti u ChatGPT.

Garmin Starter Access: **Push only**, bez istorijskog backfill-a. `GET /rest/activities` u Swagger dokumentaciji ne znači da imamo dozvolu za pull. **Ne prebacujemo se na Enterprise**, ne uvodimo plaćene servise niti čuvamo realne zdravstvene/sportske podatke. Postojeći ChatGPT alat prikazuje samo pet fikcionalnih aktivnosti.

## Instalacija GitHub / Render (identična prethodnim verzijama)

1. Raspakuj ZIP. Kopiraj **sadržaj `public/`** u postojeći direktorijum `public/` repozitorijuma `zbedic-tron/garminai`, uz zamenu datoteka. Nemoj praviti `public/public/`. `render.yaml` u root-u ostaje kompatibilan. Dokument `V100_START_HERE_SR.md` je objašnjenje i ne mora u `public/`.
2. GitHub → Commit changes → Render Free standardni auto-deploy.
3. `https://garminai-public-demo.onrender.com/healthz` mora prikazati **`version: 1.0.0`, `mode: DEMO_ONLY`, `garmin_oauth: NOT_CONNECTED`**.
4. `https://garminai-public-demo.onrender.com/garmin/integration/status` mora prikazati `phase: GARMIN_ACTIVITY_API_STAGING`, `push_ingestion_enabled:false`, `oauth_connect_enabled:false`, `real_garmin_data_stored:false`.
5. `https://garminai-public-demo.onrender.com/auth/chatgpt/status` treba i dalje da potvrdi da je privatni ChatGPT konektor dostupan i da `chatgpt_config_issues` nije popunjen. **Ne menjati OAuth klijenta, redirect URI ni ChatGPT plugin.**
6. Interni `/auth/oauth-test` → prethodni `PASS`. U ChatGPT-u pitaj već povezani **GarminAI MCP**: „Pozovi `get_sync_status` i `get_activities`. Prikaži samo stvarne odgovore alata, potvrdi DEMO_ONLY.“
7. Nemoj testirati `POST /garmin/push/activities` stvarnim podacima. Namerni odgovor je 503, ne 200.

## Šta treba razjasniti pre stvarnog Garmin push-a

- Iz *odobrenog partner materijala za Activity API* proveriti **verifikaciju porekla push zahteva** (potpis/zaglavlja/mTLS/IP / drugi dokumentovani mehanizam) i tačne primere za Activities, Details, Files, deregistration i promenu dozvola. Ne izmišljati `X-Garmin-Signature` niti koristiti samo nepouzdani `userId` iz tela za identitet korisnika.
- Potrebno je stvarno OAuth povezivanje inicirano iz validnog Neon korisničkog konteksta, jednokratni PKCE state, bezbedno spremanje šifrovanih/rotirajućih Garmin tokena, server-side Garmin `userId` → Neon `sub` veza u trajnoj bazi, izmena dozvola i brisanje naloga.
- Bezbedan idempotentni upis, RLS test sa dva prava naloga, ograničenja resursa besplatnog Render/Neon plana, i revizija Garminovih ugovornih zahteva za analizu podataka preko trećeg AI servisa.
- Tek kada svi uslovi prođu, u Garmin API Tools → Endpoint Configuration uključiti konkretne HTTPS URL-ove, potvrditi isporuku pomoću Data Generator-a i **tek potom** obraditi stvarne aktivnosti. Odobrenje Garmin aplikacije nije dokaz da je webhook spreman.

## Lokalna provera

```
cd public
PYTHONPATH=. python -m unittest discover -s tests -p 'test_*.py' -q
node tests/js/test_chatgpt_oauth_v090.cjs tests/js/oauth_ui_v086.js
node tests/js/test_login_flow.cjs tests/js/google_login_v0843.js
node tests/js/test_oauth_e2e_v087.cjs tests/js/oauth_e2e_v087.js
node tests/js/test_oauth_ui_v086.cjs tests/js/oauth_ui_v086.js
```

Produkcioni MCP transport se ne može potvrditi ovom lokalnom proverom ako paket `mcp` nije instaliran; zato obavezno ponoviti E2E kroz Render i ChatGPT posle deploy-a.

## Povratak

Ako Render ili postojeći MCP plugin ne rade, ponovo uploaduj kompletan provereni ZIP **v0.9.2** u GitHub pa uradi Commit/Render deploy. **Nema novih SQL migracija, novih Render env promenljivih, promena Garmin Portala ili plaćenih planova** koje bi trebalo poništavati.

Referentno: https://developerportal.garmin.com/sites/default/files/OAuth2PKCE_1.pdf i https://developerportal.garmin.com/developer-programs/connect-developer-api. Privatni Garmin push ugovor (autentifikacija i primeri) mora se posebno pregledati u tvom Developer Portalu.
