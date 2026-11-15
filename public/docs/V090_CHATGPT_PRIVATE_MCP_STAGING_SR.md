# GarminAI Public v0.9.0 — ChatGPT private MCP staging (0 € politika)

Ovaj ZIP je **kompletan paket**, nadogradnja prethodno uspešno testirane verzije **v0.8.9**. Sadrži prethodne Python module, demo podatke, testove i dokumentaciju. Ne zahteva ručno uređivanje koda. **Ne objavljuje plugin javno, ne čita Garmin Connect, ne aktivira realne MCP alate, ne zadržava access tokene**.

## 1. GitHub → Render (kao ranije)

1. Raspakuj ZIP.
2. Prekopiraj **sadržaj `public/`** u istoimeni direktorijum repozitorijuma `zbedic-tron/garminai`; zameni postojeće fajlove. Glavni `render.yaml` je zadržan na **Free** planu; nema novih zahtevanih biblioteka, SQL migracija ni promena Build/Start komandi.
3. **Commit changes** i potvrdi uspešan automatski deploy u Renderu.
4. `https://garminai-public-demo.onrender.com/healthz` treba da prikazuje `"version":"0.9.0"`, `"mode":"DEMO_ONLY"`, `"garmin_oauth":"NOT_CONNECTED"`.
5. `https://garminai-public-demo.onrender.com/auth/mcp-oauth/status` treba da vrati `mcp_demo_oauth_tools_enabled: true` i `mcp_demo_oauth_config_issues: []`.
6. Pokreni **nov** interni E2E test preko `https://garminai-public-demo.onrender.com/auth/oauth-test`. Stari OAuth testni klijent mora i dalje dati **PASS**. Ako ne prođe, ne nastavljaj sa ChatGPT povezivanjem.

## 2. Šta je dodato u v0.9.0?

- **Zasebno, podrazumevano isključeno** ChatGPT OAuth povezivanje, uz eksplicitni operator allowlist (Client ID + tačan callback URI). Podrazumevani v0.8.9 klijent i callback ostaju netaknuti.
- OAuth login i Consent staging stranice biraju **samo** dva unapred odobrena klijenta; zahtev i dalje validira Neon potpisom (`sig` / `oauth_query`). Zabranjeni su proizvoljni callback, scope sa Garmin pristupom i nepoznati OAuth klijenti.
- Konačan povratak na ChatGPT callback dozvoljen je samo na tačno konfigurisan HTTPS URI, uz poklapanje `state` i OAuth kod ili odbijanje. Zadržane su zaštite od ponavljanja sesije i PKCE S256.
- MCP gateway priznaje odvojeni ChatGPT Client ID **tek nakon potpune JWT verifikacije** (potpis, issuer, audience/resource, rok, `scope`, `azp`, subjekt). Ne koristi korisnički upisan ID. Za alate su i dalje dostupne **samo izmišljene, privremeno izolovane aktivnosti**.
- Objavljuje i `/.well-known/oauth-protected-resource` alias, uz postojeći `/.well-known/oauth-protected-resource/mcp-oauth-staging`. Ne prepisuje Neonovu OAuth authorization-server metadata.
- Novi bezbedan status: `https://garminai-public-demo.onrender.com/auth/chatgpt/status`, bez tajnih podataka.

## 3. Konfiguracija ChatGPT private plugina — preko interfejsa

**Ne uključuj ChatGPT staging flag dok ne budu tačni Client ID i callback.** Postojeći E2E klijent je namenjen samo za Render callback i **ne sme** da se prenameni za ChatGPT.

1. U ChatGPT veb aplikaciji otvori **Plugins → + → Add custom MCP server** (dostupnost zavisi od naloga i workspace dozvola). Odaberi **privatni/personal** plugin, *ne javni listing*. Server URL:

   `https://garminai-public-demo.onrender.com/mcp-oauth-staging`

   Authentication: **OAuth**. Ako ChatGPT traži metod, za ovu verziju koristi **predefined / static OAuth client**, a ne automatski CIMD/DCR. DCR/CIMD u Neon managed okruženju nisu testirani; aplikacija ih ne uključuje. **Preuzmi tačnu OAuth Redirect URI koju ChatGPT prikazuje za TU konekciju**. U novom režimu to može biti callback-specifičan URI, nemoj pretpostavljati stari stabilni.

2. U **Neon Console**, ista `auth-staging` grana i OAuth clients sekcija, napravi **novog** klijenta `GarminAI ChatGPT Private Demo` sa istim staging resource-om:

   `https://garminai-public-demo.onrender.com/mcp-oauth-staging`

   Postavi **Redirect URI** tačno kako je ChatGPT prikazao; `Skip consent` **OFF**, `Disabled` **OFF**. Klijent treba da bude **public** sa token auth `none`, PKCE/S256. Ako UI ne dopušta public klijenta ili callback, prekini i pošalji screenshot pre bilo kakvih izmena. Ne koristi Client Secret u ovoj verziji. Sačuvaj novi Client ID.

3. U Render **Environment** postavi tri nova ključa:

   - `GARMINAI_CHATGPT_OAUTH_CLIENT_ID` = **novi** Client ID iz Neon Console (ne E2E ID)
   - `GARMINAI_CHATGPT_OAUTH_CALLBACK` = **tačan** ChatGPT Redirect URI iz koraka 1
   - `GARMINAI_CHATGPT_MCP_STAGING_ENABLED` = `1`

   Sačuvaj; Render će primeniti konfiguraciju. Ne menjaš stari testni ID, Neon issuer, login page, postojeće staging prekidače, niti `Skip consent`.

4. Otvori `/auth/chatgpt/status`. Uslovi: `"chatgpt_connector_enabled":true`, `"chatgpt_config_issues":[]`, `"real_garmin_access_enabled":false`. Ako nije tako, stani — ne pokušavaj prijavu.
5. Vrati se na ChatGPT personal plugin i pokušaj **Connect / OAuth sign-in**. Neon Google login → Consent → Approve → povratak u ChatGPT. Pokreni kratke upite za **`get_sync_status`**, **`get_activities`**. Rezultat sme sadržati samo `DEMO_ONLY` i izmišljene aktivnosti.
6. Ako ChatGPT ne pokaže callback pre registrovanja klijenta ili ne prihvati static/predefined client, ne improvizuj URI niti nemoj uključivati DCR na slepo. Pošalji **screenshot bez tokena/šifara** i prilagodićemo narednu iteraciju.

**Važno:** Neočekivani `scope` može zaustaviti autorizaciju. ChatGPT može da pošalje samo `openid`, ili `openid email profile` prema provider metapodacima; oba su dozvoljena u ovoj demonstraciji. Bilo koji Garmin ili write scope je zabranjen. Neon klijent mora odobravati scope-ove koje se stvarno traže; ako ne, ne proširuj ih bez razmatranja.

## 4. Konfiguracija koju NISMO menjali

- `GARMINAI_MCP_AUTH_TOOLS_STAGING_ENABLED=1` (postojeći prekidač za izmišljene MCP alate)
- `GARMINAI_MCP_OAUTH_STAGING_ENABLED=1`
- `GARMINAI_OAUTH_E2E_STAGING_ENABLED=1`
- `GARMINAI_OAUTH_UI_STAGING_ENABLED=1`
- `NEON_AUTH_STAGING_URL` i `GARMINAI_MCP_OAUTH_STAGING_ISSUER` ostaju isti potvrđeni issuer
- `GARMINAI_OAUTH_TEST_CLIENT_ID` ostaje **stari testni** Client ID
- `GARMINAI_STAGING_LOGIN_ENABLED=0`
- **Nema realnih Garmin podataka**, user RLS pristup ni produkcionih Garmin tokena; stari `/mcp` DEMO bearer gate ostaje netaknut.

## 5. Kontrola troškova i bezbednosti

- Samo postojeći GitHub / Render Free / Neon Free; bez aktivacije billing-a, dodatnih premium servisa ili naplativog OpenAI API-ja.
- **Free ne znači bez ograničenja:** Render može uspavati servis; Neon ima kvote. Testiraj retko i prati dashboards. **Pretplata na ChatGPT je posebna postojeća stavka**, nema dodatnih API poziva koje bi server naplaćivao po tokenima.
- Nema javnog objavljivanja plugina bez tvoje izričite saglasnosti. Izgubljeni tok ili nepredviđeni callback: **vrati `GARMINAI_CHATGPT_MCP_STAGING_ENABLED=0`** u Render-u.
- Za hitno zatvaranje **svih** novih demo MCP alata postavi i `GARMINAI_MCP_AUTH_TOOLS_STAGING_ENABLED=0`. Stari `/mcp` je odvojen. Revert GitHub commit na v0.8.9 po potrebi.
- Nikada ne šalji kompletne URL-ove sa `code`, `state`, `sig`, `ba_param`, `code_verifier`, JWT, sesione kolačiće, Client Secret ili Google podatke. Bezbedno je poslati screenshot statusa i poruku greške bez URL query parametara.

## 6. Šta još NIJE potvrđeno

- Novi ChatGPT klijent **nije registrovan ovom nadogradnjom**. Realni OAuth tok iz ChatGPT web UI-ja nije mogao biti testiran unapred.
- Lokalno je proverena logika allowlista, callback-a i tokena, ali **realan MCP SDK transport** nije pokrenut u ovom izvršnom okruženju (nema instaliranog `mcp`). Test na Renderu i unutar ChatGPT-a je obavezan.
- OAuth metadata Neona i callback sa ChatGPT-a mogu zavisiti od odabranog režima (CIMD/DCR/static) i stvarne server konfiguracije. Ne menjaj na slepo Neon issuer ili `authorization_response_iss_parameter_supported`.
- MCP `tools/list` i `tools/call` prošli su **interni** Render E2E test u v0.8.9, što ne znači da će se nova spoljašnja ChatGPT veza automatski uspostaviti.

Dokumentacija i detalji: `public/docs/V090_CHATGPT_PRIVATE_MCP_STAGING_SR.md`.
