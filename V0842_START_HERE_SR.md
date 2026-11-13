# GarminAI Public v0.8.4.2 — Neon social/init continuation fix

## Zašto je potreban patch
Neon `/sign-in/social` vraća HTTP 200 uz JSON `{"redirect":false,"url":"https://<tačan testni Neon Auth host>/neondb/auth/sign-in/social/init?token=..."}`. Verzija 0.8.4.1 greškom dozvoljava samo `accounts.google.com`, pa vraća `INVALID_DESTINATION`.

## Izmena
- Prihvata *isključivo* `/sign-in/social/init` na tačno onom HTTPS origin-u i osnovnoj putanji koji su unapred konfigurisani u `NEON_AUTH_STAGING_URL`, sa jednim kratkotrajnim `token` parametrom u dozvoljenom formatu.
- Zadržava usko definisanu direktnu Google OAuth putanju kao alternativu.
- Ne prihvata proizvoljne destinacije ili redirect parametre; ne loguje niti prikazuje auth tokene.
- I dalje je **browser staging**, bez MCP, Garmin OAuth i stvarnih podataka.

## Deploy
1. Otpakovati ZIP. Fajlove iz `public/` kopirati u postojeći GitHub `public/`, ne kreirati `public/public/`.
2. Potvrditi commit i sačekati Render deployment. Proveriti `/healthz`: `0.8.4.2`.
3. `GARMINAI_STAGING_LOGIN_ENABLED=1` samo za kratki test, `NEON_AUTH_STAGING_URL` ostaje testna grana. `NEON_AUTH_URL` i `DATABASE_URL` ne dirati.
4. Pokrenuti novi test sa dugmeta `Continue with Google (test)`. **Ne otvarati** raniji `init?token=` URL. Potom proveriti sesiju.
5. Ako Google ili sesija zakažu, zapisati *samo* kod greške (bez URL/token/cookie). Po završetku vratiti flag na `0`.

### Ograničenje
Neon preporučuje zvanični SDK koji upravlja verifier-om, callback-om i cookie/iframe popup mehanizmom. Ovaj mali patch omogućava sledeći korak browser dijagnostike; **ne garantuje uspešnu sesiju u svim browserima**. Konačni OAuth i MCP identitet tek treba integrisati i revidirati.
