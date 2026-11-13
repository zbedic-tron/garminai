# GarminAI Public v0.8.4 — eksperimentalni Google login, samo auth-staging

**Svrha:** proveriti može li browser da pokrene Google prijavu preko Neon Managed Better Auth na grani `auth-staging` i zatim dobije `get-session`. Ovo **nije** ChatGPT/MCP OAuth autorizacija, ne povezuje Garmin, ne izdaje AI saglasnost i ne čita aktivnosti. Koristi Neonov dokumentovani REST ugovor kao eksperiment; u ovoj verziji nije ugrađen službeni Neon JS SDK. Konačno rešenje treba da koristi zvanični Neon SDK i verifikaciju tokena na serveru.

## Koraci

1. U Neonu: grana `auth-staging` → Better Auth. `Google — Shared keys` ostaje samo za razvoj; Render domen je u `Your trusted domains`; `Allow Localhost` može ostati OFF. **Ne uključuj** OAuth Provider za MCP.
2. Na GitHub-u kopiraj nove fajlove iz `public/` u istoimeni direktorijum i potvrdi commit. Render treba da prikaže verziju **0.8.4** na `/healthz` i prethodni DB/Auth PASS. Zasad nema novih env promenljivih, a testna stranica ostaje isključena.
3. U Render Environment dodaj **NEON_AUTH_STAGING_URL**: kopiraj **Auth URL sa grane auth-staging**, ne produkcioni `NEON_AUTH_URL`, ne JWKS URL i ne database connection string. Taj URL je javan i ne sadrži tajnu.
4. Dok testiraš, dodaj **GARMINAI_STAGING_LOGIN_ENABLED=1** i sačuvaj/deploy. Otvori `https://garminai-public-demo.onrender.com/auth/staging/google`.
5. Klikni **Continue with Google (test)**, koristi testni Google nalog, pa **Check Neon session**. Ako sesija nije aktivna ili Google ne otvori prijavu, sačuvaj samo nesenzitivnu poruku sa stranice (nikako URL sa kodom, kolačiće ili tokene). Neki browseri blokiraju cross-site session cookies; ovaj dokaz koncepta u tom slučaju neće raditi i trebaće podržani same-origin proxy/SDK tok.
6. Kada završiš, stavi **GARMINAI_STAGING_LOGIN_ENABLED=0**. Možeš ostaviti testnu Auth URL promenljivu, ali ona nema nikakvu funkciju kada je test isključen.

## Bezbednosne granice

- Ova stranica ne prijavljuje korisnika na GarminAI MCP i ne proverava pristupne tokene u Python procesu.
- Ne dodeljuje prava na `garminai.*` tabele; demo alatke i dalje vraćaju samo izmišljene podatke.
- Browser direktno kontaktira Neon Auth. Ako njegov API/CORS/cookie politika ne podržava ovaj način, eksperiment treba zaustaviti; **ne isključuj CSRF/CORS zaštitu** da bi proradio.
- `auth-staging` je kopija grane `production`: ako ubuduće bude stvarnih ličnih podataka u produkciji, ne kreirati staging kopiju bez anonimizacije/pravnog osnova.
- Google Shared Keys nisu namenjeni produkciji. Funkcionalna produkciona prijava i saglasnost moraju se implementirati korišćenjem zvaničnog Neon SDK-a, sa backend proverom identiteta i testiranjem sesija.
- Kada uključiš login na javno dostupnom Render domenu, registracija u Neon staging može biti otvorena bilo kome — drži ovo uključeno samo za kratki kontrolisani test. Ako je potrebno ograničiti test na odabrane korisnike, najpre dodati posebnu server-side zaštitu pristupa.
- `NEON_AUTH_URL` i `DATABASE_URL` ostaju produkcioni i **ne menjaju se**.

## Šta se smatra uspehom

`/healthz` prikazuje `0.8.4`. Nakon Google prijave, **Check Neon session** vraća `Neon reports a signed-in test session. Not authorized for MCP.` To potvrđuje samo browser-to-Neon staging sesiju, **ne** ChatGPT/MCP OAuth ni autorizaciju za Garmin podatke.
