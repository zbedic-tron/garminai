# GarminAI Public v0.8.4.3 — Neon OAuth verifier exchange (staging)

## Šta smo ustanovili

Google prijava napravi korisnika u grani `auth-staging`, ali je stari browser kod po povratku sa Google-a uklanjao **sve URL parametre** pre poziva `/get-session`. Zvanični Neon Auth SDK koristi jednokratni `neon_auth_session_verifier` koji se mora proslediti u `/get-session` da bi se završilo uspostavljanje sesije. U prethodnoj verziji `null` rezultat je takođe lažno prikazivan kao `NETWORK_OR_CORS`.

## Šta je ispravljeno

- Pri povratku sa Google-a jednokratni `neon_auth_session_verifier` uzima se u memoriju, a URL se potom odmah čisti. Parametar se **ne prikazuje, ne loguje i ne čuva**.
- Samo povratak nakon nedavno započete prijave iz iste kartice (marker bez tajni u `sessionStorage`, važi najviše 10 minuta) sme da pozove `/get-session?neon_auth_session_verifier=...`.
- Rezultat `HTTP 200` sa JSON `null` više se ne prikazuje kao mrežna/CORS greška, nego kao neuspostavljena sesija.
- Posle prve provere dugme `Check Neon session` proverava da li je sesija sačuvana u browseru. Moguće je da jednokratna razmena uspe, ali da browser i dalje ne šalje kolačiće — to je odvojena dijagnostika.
- `/healthz` i `/` sada ispravno vraćaju `0.8.4.3`.
- Obezbeđeni su automatizovani testovi Python i simulirani browser testovi u Node.js.

## Postavljanje (samo jedan korak sada)

1. Raspakuj ZIP i kopiraj sadržaj `public/` **unutar postojećeg** GitHub `public/`. Ne praviti `public/public/`. `render.yaml` ide u koren repozitorijuma, ako ga prenosiš.
2. Potvrdi `Commit changes`; sačekaj uspešno Render postavljanje.
3. Otvori `https://garminai-public-demo.onrender.com/healthz` — sada mora biti `"version":"0.8.4.3"`.
4. **Ne uključuj još testnu prijavu.** Najpre mi pošalji rezultat `/healthz`.

## Sledeći kontrolisani test

Kada se verzija potvrdi, samo privremeno `GARMINAI_STAGING_LOGIN_ENABLED=1`; na `https://garminai-public-demo.onrender.com/auth/staging/google` započni **potpuno novu** Google prijavu. Nemoj samo ponovo učitati prethodnu stranicu: novi login mora postaviti marker u ovoj kartici. Po povratku bi trebalo automatski da piše `Finalizing Neon OAuth session…`, a zatim ili `Neon session verified ...` ili precizna poruka da sesija nije završena. Klikni `Check Neon session` radi provere trajnosti, pa posle testa vrati flag na `0`.

Ne šalji nikome OAuth query, session verifier, cookie, `DATABASE_URL`, client secret ni token.

## Granice

**Ovo je i dalje samo browser staging i uski ispravak našeg prototipa, NE produkcioni OAuth.** Ne obrađujemo Garmin podatke, ne menjamo MCP autorizaciju, ne uključujemo Neon OAuth Provider, ne diramo PostgreSQL šemu i ne tražimo dodatni plaćeni servis.

Zvanični Neon SDK ostaje naš izbor za konačnu implementaciju, uključujući kompletan callback/verifier i pouzdano serversko upravljanje sesijom. Ako browser posle razmene i dalje ne zadržava sesijski kolačić, sledeći korak je test i implementacija podržanog same-origin modela ili zvaničnog SDK proxy-ja — ne isključivanje bezbednosnih kontrola.

Reference:
- `https://github.com/neondatabase/neon-js/blob/main/packages/auth/src/core/better-auth-methods.ts`
- `https://better-auth.com/docs/concepts/cookies`
