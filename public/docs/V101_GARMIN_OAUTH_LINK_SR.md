# GarminAI Public v1.0.1 — Garmin OAuth povezivanje, privatni staging

**Polazna verzija:** v1.0.0, potvrđena na Renderu. **Instalacija:** diferencijalni ZIP, samo promenjene i nove datoteke (ispod GitHub ograničenja od 100 fajlova). **Troškovi:** radimo samo na postojećim besplatnim servisima, bez plaćenih nadogradnji.

## Šta v1.0.1 radi

- Koristi **postojeću** ChatGPT ↔ Neon OAuth konekciju (proveren JWT), ali za Garmin nalog koristi **zaseban Garmin OAuth2 PKCE/S256**.
- Novi MCP alati: `get_garmin_connection_link`, `get_garmin_connection_status`, `disconnect_garmin_account` (zahteva doslovnu potvrdu `DISCONNECT_GARMIN`). Originalna tri alata za demonstracione podatke ostaju netaknuta.
- `get_garmin_connection_link` izdaje **privatni link sa rokom 10 minuta**, tek nakon provere Neon identiteta i RLS skladišta. Link se nikad ne deli drugima.
- Stranica `/garmin/oauth/connect` prikazuje zasebnu korisničku potvrdu. Zatim preusmerava na **zvanični Garmin** authorization endpoint. Nema prikaza tokena.
- `/garmin/oauth/callback` proverava **šifrovani, vremenski ograničeni, browser-cookie-vezani** state, koristi trajnu jednokratnu evidenciju u Neon-u i zatim (samo u opt-in režimu) menja Garmin autorizacioni kod za token. Proverava Garmin `userId` i dozvolu `ACTIVITY_EXPORT` i čuva šifrovani par access/refresh tokena uz vlasnika identifikovanog proverenim Neon JWT-om.
- Može se otkazati/revokovati posebnim MCP alatom; poziva Garminov `DELETE /rest/user/registration` pre lokalnog brisanja. Ne tvrdimo da je revokacija uspešna ako Garmin nije odgovorio.
- Za svaku vezu u bazi čuva se stabilni pseudonimni ključ napravljen iz **verifikovanog** `iss` + `sub`. Nije to privremeni demo ID koji se menja na Render restartu.
- **Garmin push i svi stvarni Garmin podaci u MCP-u ostaju isključeni.** Nema učitavanja Activity API treninga, nema istorijskog backfill-a, nema Garmin podataka prosleđenih ChatGPT-u. Postojeće izmišljene aktivnosti ostaju jedine koje ChatGPT može čitati.

## Korak 1 — GitHub i Render, još BEZ povezivanja

1. Raspakuj mali v1.0.1 ZIP. Prenesi njegov **sadržaj `public/`** u postojeći `public/` i eventualni `render.yaml` u **koren repozitorijuma**. Postojeći sadržaj koji nije u ZIP-u ne diraj.
2. Uradi Commit; prati Render deployment. **Ne menjaj** Neon Auth, stari Client ID ili Garmin Endpoint Configuration.
3. `/healthz` mora imati `version: 1.0.1`, `mode: DEMO_ONLY`.
4. `/garmin/integration/status` treba da kaže `version: 1.0.1`, `oauth_link_requested: false`, `oauth_connect_enabled: false`, `push_ingestion_enabled: false`, `mcp_real_garmin_data_enabled: false`.
5. Ponovi `/auth/oauth-test` i proveru tri postojeća demonstraciona MCP alata u ChatGPT-u.
6. **Ne uključuj** `GARMINAI_GARMIN_LINK_STAGING_ENABLED` dok se ne završe priprema baze i logging podešavanje.

## Korak 2 — Neon SQL Editor (staging baza, pregledaj pre izvršavanja)

Pređi na **istu Neon bazu i branch** koji Render koristi za `DATABASE_URL`. Sa nalogom koji je vlasnik šeme izvrši **novu** migraciju `public/sql/003_garmin_oauth_used_states.sql`. Migracija dodaje samo novu tabelu za SHA-256 digeste već iskorišćenih OAuth state vrednosti. RLS je uključen i FORCE, aplikaciona uloga `garminai_app` dobija samo SELECT i INSERT. Ne sadrži stvarne aktivnosti niti tokene.

Pre uključivanja proveri da postoje prethodne tabele `garminai.athletes`, `garminai.garmin_credentials`, `garminai.ai_consent` iz `001_init.sql`, da imaju RLS/FORCE RLS, da runtime koristi **neprivilegovanu** ulogu `garminai_app` (nikad owner/superuser/BYPASSRLS). Ako se u Render Logs vidi `GARMINAI_DB_CHECK: FAIL`, zaustavi se i reši podešavanje. **Ne obaraj RLS da bi test prošao.**

## Korak 3 — Render Environment, tek nakon provere baze

Vrednosti se unose **isključivo u Render interfejs**, ne u GitHub ni u razgovor. Zadrži sve postojeće promenljive, pa dodaj/proveri:

| Variable | Value |
|---|---|
| `GARMIN_CLIENT_ID` | Vrednost iz Garmin Developer Portal → GarminAI Public → Credential |
| `GARMIN_CLIENT_SECRET` | Tajna vrednost iz istog portala (kopirati bez razmaka) |
| `GARMIN_REDIRECT_URI` | `https://garminai-public-demo.onrender.com/garmin/oauth/callback` |
| `DATABASE_URL` | Postojeći TLS URL za Neon **garminai_app** bez BYPASSRLS |
| `GARMINAI_TOKEN_ENCRYPTION_KEY` | Zaseban slučajni 32-byte ključ, URL-safe Base64, sačuvan samo u Render Secrets |
| `GARMINAI_GARMIN_LINK_STAGING_ENABLED` | **`0`** tokom instalacije; `1` tek kada su prethodne stavke proverene i kada izričito odlučiš da krene live Garmin povezivanje |

Jednokratno generisanje ključa lokalno na Windows PowerShell (ne kopiraj rezultat u ChatGPT):

```powershell
$b=New-Object byte[] 32
$rng=[Security.Cryptography.RandomNumberGenerator]::Create()
$rng.GetBytes($b)
[Convert]::ToBase64String($b).Replace('+','-').Replace('/','_')
$rng.Dispose()
```

**Sačuvaj ključ trajno** u privatnom password manageru. Njegova zamena znači da stare šifrovane Garmin veze više ne mogu da se otvore.

**Važno za logove:** OAuth query može da sadrži privremeni authorization code i state. Pre uključivanja live Garmin linka postavi Render Start Command na `uvicorn garminai_public.http_server:app --host 0.0.0.0 --port $PORT --no-access-log` (ili potvrdi da se izmenjeni korenski `render.yaml` primenio). Ne loguj Authorization zaglavlja, Garmin odgovore ni URL sa parametrima. Platformski proxy logovi su van kontrole aplikacije; ne deli ih javno.

## Korak 4 — Tek nakon aktiviranja

1. Kad status ne prijavljuje konfiguracione greške, postavi `GARMINAI_GARMIN_LINK_STAGING_ENABLED=1` u Renderu.
2. Ponovo proveri `/garmin/integration/status`: `oauth_link_requested: true`, `oauth_connect_enabled: true`, `oauth_link_config_issues: []`, **push i MCP real data false**. To je **konfiguraciona provera**, ne potvrda da je Garmin token već dobijen.
3. U privatnom razgovoru sa povezanim GarminAI MCP-om pozovi `get_garmin_connection_link`. Vratiće privatni HTTPS link; ne šalji ga nikome. Otvori ga u istom pregledaču, potvrdi nastavak, zatim Garmin autorizaciju.
4. Po povratku na `/garmin/oauth/callback`, očekujemo potvrdu da je veza napravljena. U ChatGPT-u pozovi `get_garmin_connection_status`, koji daje samo `linked: true/false`, bez tokena ili identifikatora.
5. **Ne uključuj nijedan Garmin API Tools Endpoint Configuration push URL** i ne očekuj stare treninge.
6. Ako ne radi, pošalji samo bezbedni tekst greške ili status, **nikada** `code`, `state`, `ticket`, Garmin client secret, refresh/access token ili URL sa query parametrima.

## Ograničenja, bezbednost i povratak na staro

- Stvarna Garmin OAuth razmena, stvarna Neon baza, Garmin dozvole i reset/revoke još nisu provereni uživo. Lokalni testovi koriste lažne korisnike, token vrednosti i HTTP mockove; nisu dokaz odobrenja ili ponašanja pravog Garmin API-ja.
- Odobren Starter je **push-only, bez istorijskog backfill-a**. Ne koristimo Enterprise Ping/Pull.
- Uslovi Garmin→AI/ChatGPT ostaju za posebnu proveru; ova verzija **ne prosleđuje stvarne Garmin podatke ChatGPT-u**.
- Ako je potreban hitan rollback: vrati `GARMINAI_GARMIN_LINK_STAGING_ENABLED=0` i deploy. Već izdate Garmin dozvole se time **ne opozivaju**: koristi `disconnect_garmin_account` pre isključivanja ili opozovi GarminAI u Garmin Connect podešavanjima. Ne briši šifrovane kredencijale bez plana revokacije.
- Ne pokreći javno objavljivanje plugina. Nastavljamo isključivo privatno na postojećim free planovima. Ne prihvataj nikakvu naplativu funkciju.
- Garmin OAuth specifikacija (preuzeta 2026-11-15): https://developerportal.garmin.com/sites/default/files/OAuth2PKCE.pdf; token endpoint `https://connectapi.garmin.com/di-oauth2-service/oauth/token`.

## Testiranje

- Python: `cd public && python -m pytest -q tests`
- Browser (Node):
  - `node tests/js/test_chatgpt_oauth_v090.cjs tests/js/oauth_ui_v086.js`
  - `node tests/js/test_login_flow.cjs tests/js/google_login_v0843.js`
  - `node tests/js/test_oauth_e2e_v087.cjs tests/js/oauth_e2e_v087.js`
  - `node tests/js/test_oauth_ui_v086.cjs tests/js/oauth_ui_v086.js`

**Očekivano posle samog deploya:** Garmin povezivanje još nije uključeno. To je namerna zaštita.
