# GarminAI Public v0.5 — priprema zvaničnog Garmin OAuth

## Šta je isporučeno
- PKCE S256/verifier/state, 10-minutni TTL za state i URL za autorizaciju.
- Zamena authorization code za access/refresh token i rotacija refresh tokena,
  sa HTTP klijentom koji se može testirati bez stvarnih akreditiva.
- Čitanje stabilnog Garmin API `userId` i dozvola kroz dokumentovane krajnje tačke.
- Preliminarna validacija veličine/JSON formata push obaveštenja, bez prijema podataka.
- `/integration/readiness` (samo boolean statusi, bez tajnih vrednosti).
- `/garmin/oauth/callback` vraća HTTP 503 dok se ne završe identitet, baza, saglasnost i sigurni tokeni.
- Postojećih šest DEMO MCP alatki i stručna literatura ostaju netaknuti.

## Šta još NE radi
- Nema javnog Garmin Connect dugmeta, nema stvarnog OAuth povezivanja.
- Nema prijema push aktivnosti niti skladištenja stvarnih Garmin podataka.
- Nema autentifikacije pojedinačnih korisnika kroz ChatGPT.
- Nema produkcione Postgres baze niti enkripcije tokena; SQLite prototip iz v0.4 ostaje izolovan.
- Nema potvrde da Garmin dopušta prenos podataka trećem AI servisu; ne slati Garmin podatke OpenAI dok se to ne razjasni.

## Garmin portali / specifikacija
Garminova OAuth 2.0 PKCE specifikacija:
https://developerportal.garmin.com/sites/default/files/OAuth2PKCE_1.pdf

Authorize: https://connect.garmin.com/oauth2Confirm
Token: https://diauth.garmin.com/di-oauth2-service/oauth/token
User ID: https://apis.garmin.com/wellness-api/rest/user/id
Permissions: https://apis.garmin.com/wellness-api/rest/user/permissions

Obavezno proveriti najnoviju verziju privatne dokumentacije na Garmin Developer Portalu
pre prvog živog povezivanja. Starter Activity API = push-only bez istorijskog backfill-a.

## Važna arhitekturna granica
Budući OAuth tok mora početi tek kada sistem ima provereni identitet korisnika.
State/verifier se vezuju za *taj* identitet, traju kratko, troše se tačno jednom,
i čuvaju se na trajnom skladištu, ne u memoriji Render Free instance.
Callback proverava state pre nego što pošalje kod na token endpoint.
Refresh tokeni se čuvaju šifrovano u trajnoj bazi i rotiraju atomarno.
Garmin `userId` se koristi za povezivanje push obaveštenja, ne access token.
Pre povezivanja mora postojati privatni kanal za brisanje naloga i Garmin revoke.

## Render / GitHub koraci
1. Raspakuj ZIP. Postavi `public/` u postojeći `public/`, `render.yaml` u root.
   Ne pravi `public/public/`. Ne diraj statički sajt i Windows GarminAI.
2. U GitHub-u potvrdi commit; Render automatski objavljuje.
3. Proveri `/healthz` — verzija 0.5.0, `DEMO_ONLY`.
4. Proveri `/integration/readiness` — `garmin_connect_enabled` mora biti false.
5. `/garmin/oauth/callback` mora vratiti HTTP 503. To je namerno.
6. MCP Inspector sa ranijim DEMO Bearer tokenom i dalje vidi šest alatki.
7. U v0.5 ne dodaj Garmin Client ID/Secret u Render: još nema živog toka.

## Predlog za v0.6
Trajni PostgreSQL, izolacija korisnika, šifrovano čuvanje tokena,
backend OAuth klijentski identitet i consent UI. Poseban test potvrđenog
Garmin push payload formata pre obrade aktivnosti.
