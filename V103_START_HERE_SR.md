# GarminAI Public v1.0.3 — Garmin OAuth Chrome CSP redirect-chain fix

## Zašto

Na Chrome-u v1.0.2 klik na „Nastavi na Garmin“ radi i server vraća HTTP 303,
Garmin zatim vraća 302 i 307, ali browser zbog `Content-Security-Policy: form-action`
blokira konačnu navigaciju. CSP u konzoli navodi originalnu `/garmin/oauth/authorize`
adresu iako je zahtev već uspešno otišao.

## Šta je ispravljeno

- `POST /garmin/oauth/authorize` sada posle CSRF, ticket i PKCE provera vraća **200 HTML**
  na sopstvenom domenu, umesto **303** u cross-origin redirect chain.
- Stranica ima HTML `<meta http-equiv="refresh">` koji pokreće **novu top-level navigaciju**
  na striktno proverenu `https://connect.garmin.com/oauth2Confirm` adresu.
- Na stranici postoji i link kao rezerva ako automatsko preusmeravanje ne radi.
- `form-action 'self'` ostaje strogo ograničen na naš domen. Nema JS-a ni dozvole
  za proizvoljne Garmin poddomene.
- `Cache-Control: no-store`, `Referrer-Policy: no-referrer`, kratkotrajan šifrovani
  `state`, PKCE, browser cookie i jednokratna potrošnja OAuth callback-a ostaju.
- Stvarne Garmin aktivnosti i push ingestion i dalje su isključeni.

## Instalacija — mali delta ZIP

1. Raspakovati ZIP i prekopirati sadržaj `public/` preko postojećeg `public/` u GitHub-u.
2. Commit i sačekati Render deploy, proveriti `/healthz` = `1.0.3`.
3. U ChatGPT-u ponovo pozvati `get_garmin_connection_link` za **nov privatni link**.
4. Otvoriti link, kliknuti „Nastavi na Garmin“, proveriti da se otvori zvanični Garmin
   domen, proći prijavu i saglasnost. Zatim samo `get_garmin_connection_status`.
5. Ako ne radi, Chrome F12 → Console / Network sa Preserve log. Poslati samo
   host/domene i HTTP statuse, nikada kompletne URL-ove, state, code, tokene ili cookie.

## Namena i ograničenja

Ovo je ciljano otklanjanje browser CSP prepreke, ne garancija uspešnog Garmin callback-a.
Ne zahtevaju se nova SQL migracija, Garmin API Tools promene ni Render env promenljive.
Nemoj uključivati Garmin push endpointove ili MCP pristup stvarnim podacima.
Politika dodatnih troškova: **0 €**.
