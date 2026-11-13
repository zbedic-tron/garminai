# GarminAI Public v0.8.4.1 — popravka Google sign-in pokretanja

Ranija verzija je svaki problem prikazivala kao opštu grešku, bez razlikovanja HTTP odgovora i browser/CORS blokade.

Promene:
- `POST /sign-in/social` koristi dokumentovani `disableRedirect:true`; browser dobija JSON autorizacionu adresu umesto da pokušava pratiti OAuth redirect preko `fetch()`.
- Nikad ne prati HTTP preusmeravanja preko `fetch()`.
- Prikazuje samo kontrolisane kodove greške: `HTTP_400`, `HTTP_403`, `NETWORK_OR_CORS`, `INVALID_RESPONSE`, `INVALID_DESTINATION`; nikad podatke o sesiji, tokenima, URL sa kodom ili sirove server poruke.
- Navigacija je dozvoljena samo prema `https://accounts.google.com` (bez drugih domena).

## Postavljanje
1. Kopiraj sadržaj `public/` u postojećih `public/` na GitHub.
2. Sačekaj deployment i proveri `/healthz` = `0.8.4.1`.
3. Neka `NEON_AUTH_STAGING_URL` ostane iz grane auth-staging. Test uključi samo kratko: `GARMINAI_STAGING_LOGIN_ENABLED=1`.
4. Klikni Continue with Google. Ako ne uspe, pošalji **samo kod u uglastim zagradama**.
5. Po završetku vrati `GARMINAI_STAGING_LOGIN_ENABLED=0`.

Ako je kod `NETWORK_OR_CORS`, u Chrome DevTools (F12, Network) proveri status zahteva `sign-in/social` i bez kopiranja celog request/response URL, cookie/headera ili tela odgovora. Ne isključuj CORS ili CSRF kontrole.

**Ograničenje:** ovo je probni browser-to-Neon tok, bez prijave u MCP i bez Garmin podataka; cross-site kolačići i dalje mogu sprečiti sesiju čak i ako Google login krene. Pre produkcije neophodna je integracija podržanog Neon SDK-a i backend provera identiteta.
