# GarminAI Public v0.8.6 — Neon OAuth Login & Consent UI (STAGING)

**Status: implementirano i lokalno testirano, ali NE i potvrđeno stvarnim Neon OAuth Providerom.**
Ovo nije uključivanje MCP korisničkog pristupa ni Garmina. Sve alatke `/mcp` i dalje koriste samo fiktivne demo podatke, iza dosadašnje demo zaštite. `/mcp-oauth-staging` iz v0.8.5 ostaje isključen.

## Šta je implementirano

- `garminai_public/oauth_ui_staging.py`:
  - `/auth/login`: Google prijava sa proverom potpisanog OAuth zahteva kod Neona; jednokratni `neon_auth_session_verifier` menja se preko `/get-session`; zatim `/oauth2/continue` sa originalnim potpisanim `oauth_query`.
  - `/auth/consent`: prikazuje proverene podatke klijenta, `openid` i tačan `resource`; ručno **Approve** ili **Deny** poziva `/oauth2/consent`, a odluku autorizacionog servera sprovodi Neon.
  - `/auth/oauth-ui.js`: lokalni JS bez tokena i tajni; koristi zvanične Better Auth API putanje, ne implementira sopstvenog OAuth providera.
  - `/auth/oauth-ui/status`: samo javni pokazatelji konfiguracije, bez vrednosti tajni.
- `GARMINAI_OAUTH_UI_STAGING_ENABLED` je **novi** opcioni prekidač. Podrazumevano ne postoji, pa su Login i Consent *još uvek statičke, neaktivne stranice* iz v0.8.5; JS vraća 404.
- Rukovanje potpisanim zahtevom: samo `ba_param`-deklarisana polja i `sig` se prosleđuju u `oauth_query`. URL parametri nikada se ne prikazuju u HTML-u ili logovima; verifikator se uklanja iz adrese pre bilo kakve dalje akcije.
- Pre prikaza i slanja saglasnosti potreban je **pozitivan odgovor** Neon `POST /oauth2/public-client-prelogin` na originalni `oauth_query`. Taj endpoint proverava potpis i ID klijenta; za njega OAuth Provider zahteva `allowPublicClientPrelogin=true`. Ako endpoint nije dostupan ili odbije potpis, dugmad ostaju onemogućena. **Bez zaobilaženja provere.**
- Početni strogi opseg: *samo* `scope=openid`, `resource=https://<Render hostname>/mcp-oauth-staging`, `response_type=code`, `code_challenge_method=S256`, HTTPS `redirect_uri`. Zahtevi za druge opsege ili resurse se odbijaju; Garmin ne može biti obuhvaćen.
- Svako odobravanje i odbijanje zahteva eksplicitan klik, a izdavanje koda, registracija klijenta i dozvole ostaju pod kontrolom Neona. Naziv klijenta je onaj koji je **registrovao sam klijent**; korisnik treba proveriti prikazani povratni domen.

## Zašto je ovo odvojena faza

Neon Managed Better Auth OAuth Provider **nije uključen ovim paketom**. Njegova Console konfiguracija, pouzdano izdavanje OAuth tokena i kompatibilnost sa ChatGPT-om tek treba da se potvrde. OAuth UI je opt-in staging integracija, a ne završena produkciona autentifikacija.

Neon / Better Auth dokumentacija:
- https://better-auth.com/docs/plugins/oauth-provider/sign-in-flow
- https://github.com/neondatabase/neon-js/blob/main/packages/auth/README.md
- https://developers.openai.com/plugins/build/auth

## Postavljanje — sada

1. Iz ZIP-a prenesi **sadržaj foldera `public/`** u postojeći `public/` na GitHub-u. Ostale fajlove iz ZIP-a **ne kopirati** preko projekata van GarminAI Public.
2. Ne menjaj Neon Console, Render Environment, PostgreSQL niti Garmin Developer credentials.
3. Posle Render deploymenta proveri:
   - `https://garminai-public-demo.onrender.com/healthz` => `version:0.8.6`, `mode:DEMO_ONLY`
   - `https://garminai-public-demo.onrender.com/auth/oauth-ui/status` => `oauth_ui_staging_enabled:false`, `provider_enabled_by_this_app:false`, `mcp_authenticated_tools_enabled:false`, `garmin_live_data_enabled:false`
   - `https://garminai-public-demo.onrender.com/auth/login` i `/auth/consent` => stare bezbedne, neaktivne stranice.

**Ne uključivati** `GARMINAI_OAUTH_UI_STAGING_ENABLED`, `GARMINAI_MCP_OAUTH_STAGING_ENABLED`, kao ni Neon OAuth Provider dok ne završimo pripremu testnog scenarija i pregled issuer-a, callback-a i tipa klijenta.

## Plan kasnijeg kontrolisanog end-to-end testa (NE izvršavati samostalno)

1. U Neon **auth-staging** grani (nikada `production`) proveriti podržanu konfiguraciju OAuth Providera, issuer, PKCE/S256, resource, CIMD/DCR, `allowPublicClientPrelogin` i da li može da koristi login/consent URL-ove na Renderu.
2. Postaviti tačne staging adrese: `https://garminai-public-demo.onrender.com/auth/login`, `https://garminai-public-demo.onrender.com/auth/consent`, i resurs `https://garminai-public-demo.onrender.com/mcp-oauth-staging`. U provideru **ne preskakati consent**.
3. Potvrditi da Neon `/oauth2/public-client-prelogin` na originalni potpisani `oauth_query` vraća registrovani javni klijent i da odbija izmenjen/istekao zahtev.
4. Tek tada uključiti `GARMINAI_OAUTH_UI_STAGING_ENABLED=1` na Renderu, izvršiti kontrolisan authorization-code + PKCE test sa testnim klijentom i **samo** `openid` dozvolom.
5. Proveriti prijavu, prikaz klijenta, eksplicitno odobravanje/odbijanje, izdavanje koda, tokene sa ispravnim `iss`/`aud`/`scope`, i prekid toka u slučajevima falsifikovanja, isteka i nepostojeće sesije.
6. Vratiti `GARMINAI_OAUTH_UI_STAGING_ENABLED=0`. **Ne aktivirati MCP alatke** dok se verifikacija tokena ne poveže sa svakim stvarnim MCP pozivom, uz izolaciju identiteta.

## Poznata ograničenja

- Testovi su simulacije HTTP odgovora i browser interakcija. **Nisu** test uživo protiv Neon-ovog OAuth Provider endpoints ili sa ChatGPT OAuth klijentom.
- Trenutna UI je ograničena na `openid` i tačan staging MCP resource; proširenje zahteva dodatni pregled obima dozvola i zasebnu AI saglasnost za Garmin podatke.
- Neon dokumentacija o potpisanom `oauth_query` i režimu `public-client-prelogin` može se promeniti. Pri prvom testu mora se potvrditi oblik svih JSON odgovora; ako se razlikuje, raditi korekcije bez izostavljanja server-side verifikacije.
- Managed Neon Provider je vlasnik OAuth potpisa; u GarminAI kodu **nema** tajnog ključa za nezavisnu kriptografsku verifikaciju potpisanih `oauth_query` vrednosti.
- Bezbjednost korisničkih podataka i produkcioni rad zahtevaju zaseban pen-test/reviziju, autentifikaciju za MCP, povezivanje subjekta sa RLS i evidenciju korisničkog pristanka. Sam UI ne ispunjava te zahteve.
