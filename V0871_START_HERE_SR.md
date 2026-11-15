# GarminAI Public v0.8.7.1 — Neon OAuth login/consent ispravka

## Šta rešava

U v0.8.7 OAuth test dolazio je do `/auth/login`, ali se zaustavljao na `POST /oauth2/public-client-prelogin` sa **HTTP 400** (prazan odgovor). Better Auth omogućava taj endpoint samo kada je `allowPublicClientPrelogin=true`; podešavanje nije potvrđeno u Neon managed konfiguraciji.

v0.8.7.1 uklanja tu zavisnost, **ne isključuje proveru potpisa**. Neon ostaje autoritet i proverava potpisani `oauth_query` pri finalnom POST `/oauth2/consent`. Login nakon proverene sesije šalje browser nazad na Neon `/oauth2/authorize` sa tačnim, ograničenim parametrima. Consent pribavlja podatke o klijentu preko **autentifikovanog** `GET /oauth2/public-client`, nikako iz proizvoljnog naziva u URL-u.

Ovo je **staging eksperiment**, nije gotova produkciona autentifikacija. Browser ne može kriptografski da verifikuje `sig`; takvu tvrdnju kod ne daje. Kriptografsku proveru, izdavanje koda i tokena radi Neon. Dok se ne prođe stvarni E2E test i bezbednosna revizija, stvarni MCP pristup i Garmin su isključeni.

## Instalacija

1. Raspakuj ZIP.
2. Kopiraj **sadržaj `public/`** u istoimeni direktorijum repozitorijuma `zbedic-tron/garminai`, zameni izmenjene datoteke.
3. Commit → Render deploy. **Nema novih SQL migracija i nema novih Environment promenljivih.**
4. Sačuvaj postojeće Render vrednosti (ne prikazuj ih na snimku):
   - `GARMINAI_OAUTH_UI_STAGING_ENABLED=1`
   - `GARMINAI_MCP_OAUTH_STAGING_ENABLED=1`
   - `GARMINAI_OAUTH_E2E_STAGING_ENABLED=1`
   - `GARMINAI_OAUTH_TEST_CLIENT_ID` = ceo ID *već kreiranog* `GarminAI OAuth E2E Test` klijenta u Neon grani `auth-staging`
   - `NEON_AUTH_STAGING_URL` i `GARMINAI_MCP_OAUTH_STAGING_ISSUER` = već potvrđen staging issuer
   - `GARMINAI_STAGING_LOGIN_ENABLED=0`
5. Proveri `/healthz` (`version=0.8.7.1`) i `/auth/oauth-ui/status` (`oauth_ui_staging_enabled=true`, `oauth_ui_config_errors=[]`), kao i `/auth/oauth-test/status` (`oauth_e2e_test_enabled=true`).
6. U istoj kartici otvori `https://garminai-public-demo.onrender.com/auth/oauth-test` → **Start OAuth test**. Očekivani tok: Neon OAuth → GarminAI Login → Google → Neon Consent → Approve/Deny → testni callback → provera tokena. **Ovo je očekivani tok, ne potvrđen rezultat uživo.**
7. Pošalji samo tekst statusa ili bezbedan snimak bez potpisa, OAuth query-a, code-a, tokena, verifiera, session cookie-ja i tajnih vrednosti.

Ako se na Consent pojavi `HTTP_401`/`HTTP_400`, test prekini: to može biti ograničenje cross-site browser sesije ili oblika Neon odgovora. Ne pokušavaj da isključiš CORS, proveru potpisa ili `Skip consent`.

## Lokalna provera

- Python: **135 uspešnih testova**, uz **31 uspešan subtest**.
- Browser simulacije (Node): **19 OAuth UI + 8 OAuth E2E + 7 Google session = 34**.
- Puni ASGI server nije pokrenut lokalno: okruženje nema paket `mcp`; Render deployment i stvarni Neon end-to-end test ostaju neprovereni.

## Zaštite

- Samo javni staging Client ID iz Render konfiguracije; nepoznati ID odbija se.
- Samo unapred poznat povratni URL `/auth/oauth-test/callback`, scope `openid`, tačan staging MCP `resource`, `code/S256`, PKCE challenge, `state` i `prompt=consent`.
- Google callback jedino iz iste kartice i star najviše 10 minuta.
- Ograničenje ponovljenog vraćanja na `/oauth2/authorize` sprečava beskonačnu browser petlju.
- Consent ostaje eksplicitan. Neon konačno proverava kriptografski potpisani zahtev; aplikacija ne skladišti pristupne tokene.
- Postojeći `/mcp` i `garminai_app` RLS ostaju neizmenjeni.

## Ako se test završi ili zapne

Smanji javnu testnu površinu tako što u Renderu vratiš `GARMINAI_OAUTH_UI_STAGING_ENABLED=0`, `GARMINAI_OAUTH_E2E_STAGING_ENABLED=0`, `GARMINAI_MCP_OAUTH_STAGING_ENABLED=0` (po potrebi), i deploy; produkcioni OAuth ostaje odvojen.

Izvori: https://better-auth.com/docs/plugins/oauth-provider/sign-in-flow ; https://better-auth.com/docs/plugins/oauth-provider/clients ; https://better-auth.com/docs/plugins/oauth-provider/reference
