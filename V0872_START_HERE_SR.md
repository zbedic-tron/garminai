# GarminAI Public v0.8.7.2 — Neon signed query fix

## Kratko

Neon Auth redirect sadrži ponovljena `ba_param` polja, uključujući `ba_param=ba_param`. U v0.8.7.1 parser je pogrešno zahtevao da se **svako** potpisano polje pojavljuje jednom, čak i `ba_param`, pa je redovno prikazivao `INVALID_SIGNED_REQUEST`.

Ispravka dopušta ponavljanje `ba_param` liste, ali i dalje zahteva da su nazivi u listi jedinstveni, da svaki drugi deklarisani potpisani parametar postoji tačno jednom i da su naš testni Client ID, callback, resource, scope i PKCE format očekivani. **Browser ne proverava potpis**: pravo prihvatanje potpisanog zahteva i izdavanje tokena radi Neon.

## Deploy

1. Otpakuj ZIP.
2. Kopiraj samo sadržaj `public/` u istoimeni direktorijum GitHub repozitorijuma `zbedic-tron/garminai`; zameni postojeće fajlove.
3. Commit, pa Render deployment. `render.yaml` u ZIP-u je referentna kopija postojećeg Render Blueprint-a i ne treba je menjati ako već radi.
4. Bez SQL migracija i bez novih Environment promenljivih.
5. Poseti `https://garminai-public-demo.onrender.com/healthz` (očekujemo verziju `0.8.7.2`) i `https://garminai-public-demo.onrender.com/auth/oauth-ui/status` (`oauth_ui_staging_enabled=true`, bez konfiguracionih problema).
6. Otvori `https://garminai-public-demo.onrender.com/auth/oauth-test` i pokreni **novi** OAuth pokušaj, ne stari potpisani URL koji je već deljen ili istekao.
7. Pošalji samo tekst sledeće poruke: da li je prikazan Google Login ili Consent ekran ili drugi kod greške. Ne šalji pun URL, `sig`, `state`, `code`, PKCE verifier, cookies ili tokene.

## Testovi u ovom paketu

- 100 Python unittest testova — PASS.
- 23 OAuth UI browser simulacije — PASS, uključujući regresioni test za `ba_param=ba_param` i odbijanje duplikata `client_id`.
- 8 OAuth E2E browser simulacija — PASS.
- 7 Google session browser simulacija — PASS.
- Test sa stvarnim Neon Auth-om i puni MCP ASGI proces nisu potvrđeni. To radimo kontrolisano nakon Render deploymenta.

## Bezbednost

- Produkcioni MCP je i dalje DEMO_BEARER_GATE, Garmin OAuth nije povezan.
- Nisu uključene autorizovane MCP alatke ni stvarni Garmin podaci.
- Nisu promenjeni RLS, Neon korisnici, tajne, niti OAuth registracije.

Izvor: https://better-auth.com/docs/plugins/oauth-provider/sign-in-flow
