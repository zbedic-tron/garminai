# GarminAI Public v0.8.7.3 — Neon OAuth Session Loop Fix

## Uzrok i ispravka

Na stvarnom v0.8.7.2 testu `get-session` je vraćao HTTP 200, pa je prijavljen korisnik preusmeravan na **novi** `/oauth2/authorize`. Neon ga je vraćao na `/auth/login`, a naša zaštita je prijavila `OAUTH_SESSION_LOOP`.

Prema Neon Auth / Better Auth uputstvu, posle `getSession()` na OAuth login stranici treba pozvati `oauth2.continue({ selected:true })` sa **originalnim potpisanim** `oauth_query`. To je sada urađeno preko `POST /oauth2/continue`, sa `credentials:include`. Ne otvara se novi authorize URL niti se neprovereni URL koristi za izdavanje koda. Neon validira potpis, sesiju, klijenta, scope i sledeći korak (Consent). `selected:true` nije korisnička saglasnost i ne aktivira MCP alatke.

Zaštita od petlje je ostala: ponovna obrada istog `state` za 10 minuta se odbija; nepoznati redirect domeni, nevažeći odgovori i HTTP greške Neona odbijaju nastavak. Ostatak v0.8.7.2 je sačuvan.

## Postavljanje

1. Raspakuj ZIP i prekopiraj **sadržaj** `public/` preko postojećeg `public/` u GitHub repozitorijumu `zbedic-tron/garminai`; potvrdi commit.
2. Nakon Render deploymenta otvori `https://garminai-public-demo.onrender.com/healthz` — očekuje se `version: 0.8.7.3`.
3. Otvori `https://garminai-public-demo.onrender.com/auth/oauth-ui/status` — očekuje se `oauth_ui_staging_enabled: true` i `oauth_ui_config_errors: []`.
4. Pokreni **novi** test na `https://garminai-public-demo.onrender.com/auth/oauth-test` (nemoj koristiti URL iz starog zahteva ili deliti URL potpisa).
5. Očekivan sled: aktivna Google sesija (ili Google prijava) → Neon `oauth2/continue` → Consent ekran → Approve / Deny → testni callback. Ako dođe do greške, pošalji samo **kod greške** i, ako je relevantno, HTTP status `oauth2/continue` iz F12 Network. Ne šalji `state`, `sig`, `ba_param` vrednosti, autorizacione kodove ili kolačiće.

## Važno

- Nema promena u Render Environment, Neon Console, SQL/RLS, testnom Client ID, ili Garmin API podešavanjima.
- Staging flagovi ostaju kako su trenutno podešeni. Produkcioni `/mcp` ostaje DEMO_BEARER_GATE. Stvarni Garmin podaci i autorizovane MCP alatke **nisu uključeni**.
- Lokalni testovi potvrđuju ponašanje, ali **ne potvrđuju stvarni Neon Consent/E2E tok**. Ukoliko Neon vrati `HTTP_400` na `oauth2/continue`, ne menjati provider naslepo; proveriti samo bezbedno sanitizovanu vrstu odgovora.
- Testovi: 100 Python unittest testova, 28 UI browser simulacija, 8 E2E simulacija i 7 Google login simulacija — lokalno. Pun ASGI/MCP proces nije pokrenut u ovom okruženju jer biblioteka `mcp` nije instalirana.

Izvori:
- https://github.com/neondatabase/neon-js/blob/main/packages/auth/README.md
- https://better-auth.com/docs/plugins/oauth-provider/sign-in-flow
