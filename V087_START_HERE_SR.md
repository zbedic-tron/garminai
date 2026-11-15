# GarminAI Public v0.8.7 — NASTAVLJAMO! 🚀

**ZIP za GitHub:** kopiraj samo sadržaj foldera `public/` u postojeći `public/` repozitorijuma GarminAI, potvrdi Commit changes. Ne diraj privatnu Windows verziju.

**Prvi korak:** proveri `https://garminai-public-demo.onrender.com/healthz` (`version: 0.8.7`) i `https://garminai-public-demo.onrender.com/auth/oauth-test/status` (`oauth_e2e_test_enabled:false`). Ovo je očekivano i bezbedno stanje posle deploymenta.

**Drugi korak — NE preskakati:** na Neon grani `auth-staging` otvori Better Auth → OAuth provider → OAuth clients → Create client. Potrebni su **public/no secret**, **web**, **authorization_code**, **openid**, povezani resource `https://garminai-public-demo.onrender.com/mcp-oauth-staging` i tačan redirect URI `https://garminai-public-demo.onrender.com/auth/oauth-test/callback`. `skip consent` mora ostati isključen. Ako opcije nisu dostupne, stani i pošalji screenshot bez tajni; nemoj improvizovati.

**Tek kada klijent postoji:** u Render Environment dodaj `GARMINAI_OAUTH_TEST_CLIENT_ID=<javni ID>` i `GARMINAI_OAUTH_E2E_STAGING_ENABLED=1`. Postojeći MCP OAuth staging i OAuth UI staging ostaju uključeni; Garmin OAuth i produkcioni MCP identitet ostaju isključeni.

**Browser test:** `https://garminai-public-demo.onrender.com/auth/oauth-test` → Start OAuth test. Pokreni iz istog taba; potpisani Neon OAuth Login/Consent mora raditi. Ako se pokaže 403/404 na prelogin, ne zaobilazi zaštitu — managed Neon možda ne podržava `allowPublicClientPrelogin`.

**Kada se završi test:** vrati `GARMINAI_OAUTH_E2E_STAGING_ENABLED=0`. Ne objavljuj authorization code, state, session verifier ili access token.

Detalji, očekivanja i granice testiranja: `public/docs/V087_OAUTH_E2E_TEST_SR.md`.

### Provera paketa

```
cd public
python -m unittest discover -s tests -p "test_*.py"
node tests/js/test_oauth_e2e_v087.cjs tests/js/oauth_e2e_v087.js
node tests/js/test_oauth_ui_v086.cjs tests/js/oauth_ui_v086.js
node tests/js/test_login_flow.cjs tests/js/google_login_v0843.js
```

Ovo je **lokalno testiran alat za stvarni E2E test**, ne dokaz da je end-to-end prijava već izvršena. Stvarni Neon odgovor moramo proveriti zajedno.
