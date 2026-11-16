# GarminAI Public — KANONSKI DOSIJE v1.1.9 (pripremljeno, deployment još nije potvrđen)

**Stanje potvrđeno od korisnika pre ovog paketa:** v1.1.8, četiri stvarno izvršena sintetička MCP recovery testa PASS, završni status `ACKED_SYNTHETIC`, D1 brojač pokušaja 3. Render operator flag `GARMINAI_EDGE_RECOVERY_STAGING_ENABLED` korisnik je vratio na `0`. **v1.1.9 je pripremljen i lokalno testiran, ali nije još instaliran na Render ili potvrđen u ChatGPT MCP-u.**

## Šta donosi v1.1.9

- Privatni MCP `get_synthetic_delivery_observability`: samo stanje v1.1.8 D1 događaja za verifikovani Neon subject, `d1_claim_attempts`, `d1_acknowledged`, preostali broj *ručno dopuštenih* pokušaja, redigovana procena potrebe za intervencijom; nema korisničkog identifikatora, sadržaja, URL-ova ni tajni. Čitanje ne zahteva novi operator flag.
- MCP `run_synthetic_delivery_safe_retry`: **opciono** ručno ponavljanje postojećeg *PENDING* sintetičkog događaja, uz `confirmation=RUN_SYNTHETIC_SAFE_RETRY` i `GARMINAI_EDGE_RELIABILITY_STAGING_ENABLED=1`. `ACKED_SYNTHETIC` vraća `ALREADY_ACKNOWLEDGED`, bez Neon upisa ili D1 `claim`. Nedostajući događaj odbija umesto automatskog kreiranja. Aplikacioni limit je šest pokušaja (nije atomski D1 quota i nije bezbednost protiv konkurentnih operatora). Ovaj put ostaje isključen po podrazumevanom stanju.
- Read-only GET `/garmin/ingress/delivery-observability` prikazuje samo bezbedne konfiguracione zastavice. Ne izlaže D1 ili Neon stanje.
- **Nema nove D1 ili Neon šeme**, nema Cloudflare redeploya, novih korisničkih tajni, rotacije `BRIDGE_TOKEN`/`LAB_TOKEN`, background scheduler-a ili ulaznog Garmin webhook-a.
- Već postojeći v1.1.8 D1 zapis je ACKED: *najbolji prvi test je samo read-only MCP poziv*. Nema razloga paliti novi flag za neuspešan/prazan retry.
- Ne postoje istorijski kod poslednje greške i latencije u v1.1.8 D1 šemi. v1.1.9 **ne izmišlja** te informacije; eksplicitno ih označava kao nedostupne. Automatska isporuka, retention, upozorenja i detaljan dnevnik su odvojeni budući rad.

## Šta sledeće, posle instalacije

1. Preneti **samo delta ZIP** na GitHub (`public/` putanje), commit, zatim proveriti `/healthz` = `1.1.9`.
2. GET `/garmin/ingress/delivery-observability` -> `version=1.1.9`, `production_readiness=BLOCKED`, `operator_manual_retry_enabled=false`.
3. ChatGPT GarminAI MCP → Settings → Manage app → Refresh tools, očekivano 12 alata. Pozvati **samo** `get_synthetic_delivery_observability` i potvrditi očekivani `delivery_state=ACKED_SYNTHETIC`, `d1_claim_attempts=3`, `retry_permitted=false` (ako nema promene D1 zapisa u međuvremenu).
4. **Ne uključivati** `GARMINAI_EDGE_RELIABILITY_STAGING_ENABLED` samo radi testa na već potvrđenom zapisu. Držati ga `0` ili nepostojećim. Ostali operator flags ostaju `0`.
5. Cloudflare `wrangler.toml`, postojeću D1 bazu, Neon migracije 001–005 i Garmin OAuth **ne menjati**.

## Rizici i otvorena pitanja

- Nema garancije stvarne Garmin autentifikacije, live 30s rokova, strogog distribuiranog retry limita, automatske dostave ili dozvoljenog slanja Garmin podataka trećoj AI platformi.
- Cloudflare Worker je izolovana sintetička laboratorija, nije Garmin Endpoint Configuration destinacija.
- Koristiti samo besplatne planove, dodatni budžet 0 €, diferencijalne ZIP-ove <100 fajlova, nikad ne objavljivati tajne ili poverljive Garmin PDF-ove.

---

## PRETHODNO POTVRĐEN HANDOFF (v1.1.8 — istorija i tehnički kontekst)

# GARMINAI PUBLIC — KANONSKI DOSIJE ZA NASTAVAK RADA
**Stanje: 16. novembar 2026. | Poslednja potvrđena aplikaciona verzija: 1.1.8 | Status: sintetički end-to-end recovery PASS**

> **PROČITAJ OVAJ ODELJAK PRVI U NOVOM RAZGOVORU.** Ovaj fajl je najnoviji, usaglašeni operativni status. Stariji `PROJECT_CONTINUITY_SR.md` dodaci sadrže istorijske napomene poput „v1.1.8 nije instaliran“, koje su sada **zastarele**. Razdvoji ono što je korisnik potvrdio u stvarnom okruženju od lokalnih testova i onoga što tek treba uraditi.

## 1. POTVRĐEN POSLEDNJI KORAK — v1.1.8 RECOVERY (16.11.2026)

Korisnik je potvrdio da je:
- Nadogradio Cloudflare Worker na recovery funkcionalnost v1.1.8 u **postojećoj** D1 bazi pomoću `Install-Recovery-V118.ps1`; izlaz: `PASS: Existing synthetic Cloudflare Worker upgraded to v1.1.8.`
- Izvorna instalaciona skripta imala PowerShell parser grešku `"$Stage: ..."` i zamenjena je **v1.1.8.1 PowerShell Parser Hotfix** (samo lokalni instalacioni hotfix). **Ne vraćati staru skriptu.**
- Na Renderu privremeno omogućio `GARMINAI_EDGE_RECOVERY_STAGING_ENABLED=1`, a prethodne testne prekidače držao na `0`.
- Zatražio i dobio preko povezanog, autentifikovanog **GarminAI MCP** četiri stvarno izvršena sintetička scenarija redom:

| Scenario | Rezultat koji je stvarno vratio MCP | Prateća read-only provera |
|---|---|---|
| `SIMULATE_RENDER_DELAY` | `SIMULATED_RENDER_DELAY_D1_PENDING`; `neon_write_attempted:false`, `d1_acknowledged:false`, `retry_safe:true` | `PENDING_SYNTHETIC`, `d1_claim_attempts:0` |
| `SIMULATE_NEON_UNAVAILABLE` | `SIMULATED_NEON_UNAVAILABLE_D1_PENDING`; `neon_write_attempted:false`, `d1_acknowledged:false`, `retry_safe:true` | `PENDING_SYNTHETIC`, `d1_claim_attempts:1` |
| `SIMULATE_D1_ACK_UNAVAILABLE` | `SIMULATED_D1_ACK_UNAVAILABLE_NEON_COMMITTED`; `neon_committed_or_existing:true`, `d1_acknowledged:false`, `retry_safe:true` | `PENDING_SYNTHETIC`, `d1_claim_attempts:2` |
| `RECOVER` | **`status:PASS`**; `neon_committed_or_existing:true`, `neon_duplicate_prevented:true`, `d1_acknowledged:true`, `d1_claim_attempts:3`, `subject_scoped:true` | **`ACKED_SYNTHETIC`**, `d1_acknowledged:true`, 3 pokušaja |

Potvrda za svaki MCP scenario: `confirmation="RUN_SYNTHETIC_DELIVERY_RECOVERY"`. Rezultat poslednjeg statusnog poziva bio je `neon_independently_queried:false`: dakle statusni alat ne predstavlja zasebnu SQL verifikaciju Neona; oslanjamo se na autentifikovani MCP rezultat. Scenariji su **simulacije preskočenih koraka** — nisu izazvani stvarni prekidi Rendera ili Neona. Nema automatskih pokušaja u pozadini; obrada se pokreće MCP pozivom.

**Poslednja korisnička potvrda:** `GARMINAI_EDGE_RECOVERY_STAGING_ENABLED=0` je vraćen nakon testiranja. Nije izvršena nova nezavisna provera vrednosti posle tog poteza; po potrebi proveriti kroz Render dijagnostiku. Ostali testni prekidači takođe treba da ostanu 0.

## 2. STATUS SISTEMA / ARHITEKTURA

- **GitHub**: `zbedic-tron/garminai`, projektni kod u `public/`; korisnik kopira sadržaj diferencijalnog ZIP-a na postojeće putanje GitHub web interfejsom.
- **Render Free**: `https://garminai-public-demo.onrender.com` — Python MCP server, `/healthz`, `/garmin/ingress/readiness`, `/garmin/ingress/delivery-recovery`. Pokretanje tipično `uvicorn garminai_public.http_server:app --host 0.0.0.0 --port $PORT --no-access-log`. Poslednje potvrđena aplikaciona verzija v1.1.8; pre novih izmena proveriti `/healthz` jer implementacija može biti ažurirana u međuvremenu.
- **ChatGPT privatni plugin**: `GarminAI MCP` → `https://garminai-public-demo.onrender.com/mcp-oauth-staging`; autentifikacija Neon OAuth + PKCE/CIMD. **10 alata** zaključno s v1.1.8. Promene liste: Settings → Manage app → Refresh tools.
- **Neon PostgreSQL**: schema `garminai`, role `garminai_app`, RLS i FORCE RLS, subject-scoped pristup; SQL migracije 001–005 ranije izvršene. Ne ponavljati bez razloga i ne dodeljivati UPDATE/DELETE prava aplikaciji samo zbog sintetičkog testa.
- **Cloudflare Workers Free + D1**: `https://garminai-synthetic-edge-v116.zbedic.workers.dev`, baza `garminai-synthetic-edge-v116`, Worker nadograđen v1.1.8. Izolovana sintetička šema za v1.1.6 / bridge v1.1.7 / recovery v1.1.8; D1 ACK posle potvrđenog Neon upisa. **Cloudflare nije podešen kao Garmin destinacija**.
- **Garmin OAuth**: Garmin Developer aplikacija sa Starter Activity API, povezivanje naloga ranije nezavisno potvrđeno preko MCP `get_garmin_connection_status`: `linked:true`, `status:STAGING_ONLY`, `activities_access:false`, `ai_sharing:false`. `/healthz` poruka `garmin_oauth:NOT_CONNECTED` odnosi se na DEMO kontekst i ne poništava ovu nezavisnu proveru.

### Uspešne istorijske etape
- v1.1.1: Neon inbox tabela + RLS/FORCE RLS, `GARMINAI_DB_CHECK: PASS` potvrđen.
- v1.1.2 → v1.1.3: `STORAGE_NOT_READY` otklonjen uklanjanjem nedozvoljenog `FOR UPDATE` iz aplikacione uloge bez UPDATE prava; sintetički Neon test zatim PASS.
- v1.1.4: fail-closed dijagnostika live Garmin ingress-a; readiness `BLOCKED`.
- v1.1.5: sintetički edge prototip, bez deploymenta.
- v1.1.6 / lokalni hotfixi 1.1.6.1–1.1.6.4: Cloudflare Workers Free + D1 objavljeni; stvarni sintetički test **200/200/409** i trajni D1 upis PASS; hotfixi su rešavali PowerShell/HTTP test skriptu.
- v1.1.7: autentifikovani MCP sintetički D1 → Neon → D1 ACK, zaštita od duplikata i izolacija PASS. Zaseban HMAC pseudonim, bez Garmin ID u D1.
- **v1.1.8: četiri recovery scenarija PASS, završni read-only `ACKED_SYNTHETIC`.**

### Tajne i konfiguracija (NE NAVODITI VREDNOSTI)
- Render: `GARMINAI_EDGE_BRIDGE_URL`, `GARMINAI_EDGE_BRIDGE_TOKEN`, `GARMINAI_EDGE_BRIDGE_STAGING_ENABLED=0`, `GARMINAI_EDGE_RECOVERY_STAGING_ENABLED=0`, `GARMINAI_PUSH_REHEARSAL_STAGING_ENABLED=0`.
- Cloudflare: `BRIDGE_TOKEN` i `LAB_TOKEN`, postavljeni kao tajne, bez upisa u GitHub; postojeća konfiguracija i D1 baza moraju se očuvati. Ne rotirati tajne bez razloga.
- Ne objavljivati: OAuth code/state, Client ID/Secret kad su osetljivi, JWT, DATABASE_URL, API ključeve, encryption key, lične Garmin podatke ili poverljive Garmin PDF dokumente.

## 3. TVRDA BEZBEDNOSNA I BUDŽETSKA PRAVILA

1. **0 € dodatnih troškova**. Besplatni postojeći planovi; nikakva plaćena pretplata/Enterprise/upgrade bez eksplicitnog dogovora. Proveravati kvote i naplatu pre novih resursa.
2. **Diferencijalni ZIP <100 fajlova**, idealno mnogo manje (GitHub browser upload ograničenje). Ne nuditi ponovno celog repoa. Svaki ZIP mora očuvati postojeće `public/` putanje.
3. **Nema stvarnog Garmin push prijema**, Garmin Endpoint Configuration ostaje isključena; javni ingress fail-closed (`503`), `/garmin/ingress/readiness` ostaje `BLOCKED`.
4. **Nema Garmin aktivnosti u AI** i nema stvarnih/izvedenih Garmin podataka u ChatGPT-u ili Cloudflare-u bez zasebne provere prava, privatnosti i ugovornog odobrenja. Developer License Agreement Rev H posebno reguliše AI, obradu kod trećih strana i poverljivost. Nije dovoljno samo korisničko OAuth odobrenje.
5. Garmin Starter Activity API je **PUSH_ONLY** bez istorijskog backfill-a. Dostupni Garmin IP opsezi u poverljivom dokumentu ne dokazuju sender authentication iza proxy-ja; ne verovati slepo `X-Forwarded-For`. Render Free uspavljivanje može trajati duže od Garminovog 30-sekundnog push timeout-a. Laboratorijski `BRIDGE_TOKEN` nije potpis Garmin zahteva.
6. Stvarni korisnički ID i aktivnosti ne smeju se pojaviti u laboratorijskim porukama; ograničena, fikciona, identitetski pseudonimizovana testna šema.
7. Bezbedna fail-closed semantika i idempotentni ponovni pokušaji; nema tvrdnje o produkcionoj spremnosti bez realnih dokaza.
8. Ne menjati zasebnu Windows GarminAI arhivu/aplikaciju bez korisnikovog zahteva. Ne objavljivati GitHub repo ili plugin javno bez odobrenja.

## 4. SLEDEĆI RAD — PLANIRAN v1.1.9, NIJE JOŠ IZVRŠEN

**Cilj**: Synthetic Delivery Reliability / Observability, bez promena produkcionog Garmin prijema.
- Dizajnirati istoriju isporuke, broj pokušaja, poslednju grešku sa sanitizovanim kodom, poslednji ACK; status samo autentifikovanog korisnika, bez ID/payload/leak-a.
- Proveriti bezbedan retry workflow za sintetičke događaje i način nadzora kada nema interaktivnog MCP poziva. Ne obećavati background retry dok ne postoji stvarni scheduler/implementacija. Razmotriti Cloudflare Free kvote i uslove pre bilo kakvog automatizovanog pokretanja.
- Planirati D1 retention/cleanup i limiter/test izolaciju, kao i fault-injection testove koji pokrivaju eventualno ponovno pokretanje radnika.
- Produkcioni live Garmin sender authentication, autorizacija trećeg provajdera za podatke, AI pravila i 30s SLA su i dalje **nezavisni, otvoreni blokatori**. Privatni live beta datum nije garantovan.
- Pre kodiranja: proveriti `/healthz` i postojeću strukturu repoa, čitati najnoviji dosije, rekonstruisati poslednji dif ZIP, ne ponavljati već uspešne migracije i testove bez razloga.

## 5. LOKALNE PUTANJE KOJE KORISNIK KORISTI

- Windows PowerShell: `D:\Downloads\GarminAI-Public-v1.1.6\public\edge_lab_v116` (postojeći `wrangler.toml` za D1 — ne pregaziti).
- Novi Cloudflare sintetički kod je u GitHub projektu `public/edge_lab_v116/`.
- Poslednji poznati ZIP: `GarminAI-Public-v1.1.8-Synthetic-Delivery-Recovery-Delta.zip`.
- Lokalni parser hotfix za deploy: `GarminAI-Public-v1.1.8.1-PowerShell-Parser-Hotfix.zip`.
- Ovaj dokument preporučeno držati kao **aktuelni kanonski** `public/docs/PROJECT_CONTINUITY_SR.md` u projektu, ali starije istorijske dodatke čuvati odvojeno; kada se verzija menja, zameniti kanonski status, ne dodavati nove kontradiktorne „trenutne“ naslove.

## 6. JEDNA PORUKA ZA POČETAK NOVOG RAZGOVORA

> Nastavljamo razvoj **GarminAI Public** prema priloženom KANONSKOM DOSIJEU. Trenutno potvrđen v1.1.8: četiri sintetička recovery scenarija preko GarminAI MCP-a uspešno prošla, završni D1 status `ACKED_SYNTHETIC`; testni flag vraćen na 0. Prvo proveri zdravlje postojeće aplikacije i poslednji status, pa nastavi sa planiranjem **v1.1.9 Synthetic Delivery Reliability/Observability**. Zadrži 0 € dodatnih troškova, diferencijalni ZIP <100 fajlova i sve bezbednosne zaštite. Ne otvaraj stvarni Garmin push ili AI pristup aktivnostima, ne ponavljaj migracije ili OAuth povezivanje. Vodi razvoj kroz instalabilne ZIP-ove i Windows PowerShell korake.

**Ovaj fajl ne sadrži pristupne tajne.** U novom threadu ga priloži, umesto oslanjanja samo na Memory. Novi thread treba da verifikuje trenutno stanje, jer dokument sadrži poslednje *potvrđeno* stanje, a ne automatski live nadzor.
