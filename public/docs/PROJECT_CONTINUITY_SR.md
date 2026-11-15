# GarminAI Public — projektni dosije za nastavak u novom ChatGPT razgovoru

**Aktuelna pripremljena verzija: v1.1.2 (2026-11-15).** Ovaj dokument je operativno stanje i istorija projekta, a nije dokaz da je nova verzija instalirana. Prvo pogledati `/healthz` i `/garmin/integration/status` na Renderu.

> **Za novi razgovor:** „Nastavi projekat GarminAI Public prema `public/docs/PROJECT_CONTINUITY_SR.md` i aktuelnom GitHub kodu. Sačuvaj politiku 0 €, bezbednosne granice i diferencijalno pakovanje ispod 100 fajlova. Najpre proveri aktuelni `/healthz`, a zatim sledeći otvoreni korak.“

## 1) Korisnički cilj i nepromenljiva pravila

- **GarminAI Public**: privatni ChatGPT MCP servis za rekreativne trkače sa opcionalnim Garmin Connect povezivanjem; kasnije bi trebalo da pomogne analizi treninga, ali ne uvoditi realne Garmin podatke u AI bez posebne pravne/ugovorne provere.
- **0 € dodatnih troškova — strogo.** Samo postojeći besplatni planovi; ne predlagati plaćene nadogradnje, nove pretplate ili Enterprise bez izričitog dogovora. Ni Garmin Starter korišćenje ne treba smatrati trajno besplatnim bez provere uslova.
- **Bez javnog objavljivanja** bez izričitog odobrenja. Privatni ChatGPT plugin je u DEVELOPMENT režimu.
- **Ne dirati odvojenu GarminAI Windows aplikaciju**, niti uvoziti privatne lokalne Garmin arhive bez novog dogovora.
- **GitHub web upload max 100 fajlova po operaciji.** Svaka sledeća verzija: **diferencijalni ZIP** sa samo novim i izmenjenim fajlovima (idealno < 30), postojeća struktura foldera; ne pakovati ponovo kompletan repo. Uvek navesti šta se kopira i šta ostaje neizmenjeno.
- **Ne izlagati** Client Secret, DATABASE_URL, JWT, OAuth code/state, refresh tokene, AES ključ, lične podatke, Garminova poverljiva dokumenta, partner IP opsege i partner licence u javni repo ili chat.
- Korisnik radi prvenstveno kroz **GitHub web interfejs, Render Dashboard, Neon SQL Editor i Garmin API Tools**, bez uređivanja Python koda ručno. Pripremati instalabilne ZIP-ove i jasna uputstva korak po korak.

## 2) Arhitektura

- **Repo:** GitHub; Python projekat u `public/`; Render izvršava `uvicorn garminai_public.http_server:app --host 0.0.0.0 --port $PORT --no-access-log` iz `public/`.
- **Servis:** `https://garminai-public-demo.onrender.com`, `/healthz`, `/garmin/integration/status`.
- **ChatGPT MCP:** `https://garminai-public-demo.onrender.com/mcp-oauth-staging`; razvojni privatni plugin `GarminAI MCP`; Neon OAuth/CIMD + PKCE/JWT gate. ChatGPT može videti stari popis alata; `Settings → Manage app → Refresh tools` učitava nove bez kreiranja novog plugina.
- **Neon PostgreSQL:** `garminai` šema, aplikaciona neprivilegovana uloga `garminai_app`, transakciono postavljen `garminai.subject`, RLS + FORCE RLS. Render `DATABASE_URL` mora pokazivati na isti Neon branch/bazu kao SQL Editor (ranije je mismatch uzrokovao `STORAGE_NOT_READY`).
- **Garmin OAuth:** odvojen od Neon OAuth; Garmin Connect Developer aplikacija `GarminAI Public` (Starter Activity API, OAuth 2.0). Callback `https://garminai-public-demo.onrender.com/garmin/oauth/callback`. `Client ID/Secret` i encryption ključ samo Render Environment. Garmin OAuth link je browser-bound, PKCE S256, 10-minutni ticket, jedokratni state, čuvanje tokena šifrovano AES-GCM po identitetu. Povezivanje je **stvarno potvrđeno** (`get_garmin_connection_status → linked:true`).
- **Demo MCP**: `get_sync_status`, `get_activities`, `get_demo_activity_details` prikazuju IZMIŠLJENE podatke. `get_sync_status → garmin_oauth: NOT_CONNECTED` govori o demo sinhronizaciji, **ne opovrgava** zasebnu stvarnu vezu prikazanu preko `get_garmin_connection_status`.
- **Garmin konekcijski MCP alati**: `get_garmin_connection_link`, `get_garmin_connection_status`, `disconnect_garmin_account`.
- **Od v1.1.2** dodat je `run_synthetic_push_rehearsal`: izričita potvrda + operator flag; stvara najviše 1 trajni **fiktivni** zapis po verifikovanom Neon korisniku i proverava idempotenciju. Ne poziva Garmin i ne čita stvarne aktivnosti. Zahteva refresh MCP alata.

## 3) Proverene etape

- v0.8.7–v0.8.9: Neon PKCE E2E i izolovani, autentifikovani demo MCP `tools/list` + `tools/call`; odbijanje tuđeg demo ID-a.
- v0.9.1: ChatGPT CIMD povezivanje uspešno, `Primary is now connected`.
- v0.9.2: stabilan demo MCP, korisnički identitet i RLS testovi.
- v1.0.0: Garmin Activity parser offline; stvarni push blokiran.
- v1.0.1: Garmin OAuth + Neon vezivanje, migracija `003_garmin_oauth_used_states.sql`; SQL RLS/privilegije i `GARMINAI_DB_CHECK: PASS (OK)` potvrđeni.
- v1.0.2–v1.0.3: Chrome CSP blokada preusmeravanja rešena server-rendered handoff stranicom; Garmin consent ekran uspešno prikazan.
- v1.0.3: Garmin OAuth callback prikazao uspeh i MCP `get_garmin_connection_status` je vratio `linked:true, activities_access:false, ai_sharing:false`.
- v1.1.0: migracija `004_garmin_activity_push_rehearsal.sql` za `garmin_push_receipts` prošla; RLS + FORCE RLS, SELECT/INSERT `t`, UPDATE/DELETE `f`.
- v1.1.1: migracija `005_garmin_push_inbox_offline.sql` za `garmin_push_inbox` prošla; RLS/FORCE RLS/SELECT/INSERT `t`, UPDATE/DELETE `f`. Render log `GARMINAI_DB_CHECK: PASS (OK)` potvrđen tri puta. Javni Garmin push ostao `503`.
- v1.1.2: pripremljen opt-in MCP test *stvarnog Neon transakcionog upisa jednog sintetičkog reda* i duplikata. **Lokalni testovi nisu dokaz realnog Neon PASS-a; tek treba primeniti i pokrenuti alat u korisničkom okruženju.**

## 4) Bezbednosna i pravna ograničenja — ne zaobilaziti

- Garmin Starter je push-only. Javni `/garmin/push/*` ostaje zaključan (`503`) i nije konfigurisan u Garmin Endpoint Configuration. Nema istorijskog backfill-a.
- Partner Activity API dokument navodi IP opsege, ali **Render Free nema verifikovanu pouzdanu identifikaciju originalnog izvora** iza proxy-ja; `X-Forwarded-For` nije sam po sebi dokaz. Ne proglašavati IP/payload/HTTPS samostalno autentičnim webhook-om. Rešenje nije plaćeni Render plan bez odobrenja.
- Render Free spava pri neaktivnosti (buđenje može >50 s), a Garminov push ima kraći timeout. Ugovorna i operativna bezbednost i pouzdano prihvatanje pre HTTP 200 tek treba da se reše.
- Garminov Developer License Agreement Rev H ima stroga ograničenja deljenja podataka sa trećim stranama i AI (posebno 5.2 i 15.10–15.11). **Ne slati stvarne ili izvedene Garmin podatke ChatGPT-u**, pa čak ni uz korisničku saglasnost, dok nema adekvatnog pravnog/ugovornog ovlašćenja. Ovaj dokument nije pravno mišljenje.
- Garminovi poverljivi partner PDF-ovi i tekstovi ostaju van javnog GitHub-a. Materijali su pregledani u prethodnom razgovoru: `Start Guide 2.0`, `Activity API 2.1`, `License Agreement Rev H`.
- Ne uključivati u Garmin API Tools `Enabled`/`On Hold`, ni `GARMINAI_GARMIN_PUSH_ENABLED=1`, niti real MCP ingestion bez provere autentifikacije, brisanja, retencije i garminovih pravila.

## 5) Trenutna v1.1.2 instalacija i provera

1. Primeniti mali ZIP v1.1.2 preko postojećeg `public/` foldera, bez brisanja drugih fajlova; GitHub commit i Render deployment.
2. `/healthz → version: 1.1.2`, `/garmin/integration/status → push_ingestion_enabled:false, verified_live_ingress_enabled:false, mcp_real_garmin_data_enabled:false`.
3. Postojeće Neon migracije `001`–`005` su već izvršene i proverene; **nema nove SQL migracije** za v1.1.2.
4. U Render Environment dodati `GARMINAI_PUSH_REHEARSAL_STAGING_ENABLED=1` samo za kontrolisani sintetički test; ne menjati `DATABASE_URL` niti Garmin ključeve. Nakon testiranja vratiti na `0` i sačuvati.
5. U ChatGPT plugin Settings → Refresh tools; očekivati dodatni sedmi alat `run_synthetic_push_rehearsal`. Pozvati sa `confirmation: "RUN_SYNTHETIC_REHEARSAL"`. Rezultat `PASS` potvrđuje za *taj jedan povezani Neon korisnički nalog* tranzakcioni upis i ponovno slanje duplikata u stvarnoj Neon bazi. Ne dokazuje Garmin sender auth, mrežni webhook ili višekorisnički real test.
6. Po potrebi proveriti samo broj sintetičkih redova u Neon SQL Editoru: `SELECT count(*) FROM garminai.garmin_push_inbox WHERE activity_id = 'GARMINAI_SYNTHETIC_V112';` Ne objavljivati subject/garmin_user_id, tokene, ni payload.
7. Povezivanje se proverava kroz `get_garmin_connection_status`; ne treba ponovo dati Garmin saglasnost.

## 6) Budući zadaci

- Pouzdano i besplatno dokazivanje Garmin push izvora na Render edge-u ili drugi odobreni put; sačuvati fail-closed model.
- Rešiti 30-sekundni timeout naspram Render Free cold-start bez plaćene infrastrukture i bez gubitka događaja.
- Realan test više korisnika sa dva nezavisna povezana naloga i odvojena dozvola za brisanje/revokaciju.
- Obrada Garmin deregistrations i promene dozvola, retencija i brisanje; proveriti odobrenost pružalaca infrastrukture.
- Pravno rešiti eventualno korišćenje Garmin podataka u eksternom AI sistemu pre omogućavanja MCP real-data tools.

## 7) Prenos u novi thread

Ovaj dosije treba da se nalazi u GitHub-u. U novom ChatGPT razgovoru priloži aktuelni ZIP **ili** kopiraj sadržaj ovog dosijea (možeš ga i direktno uploadovati). Upit: „Nastavljamo GarminAI Public: koristi ovaj PROJECT_CONTINUITY_SR.md kao izvor stanja i proveri verziju na Renderu. Ne ponavljaj završene migracije. Radi diferencijalne ZIP-ove; 0 €; ne otvaraj realni Garmin push/AI.“

ChatGPT Memory može povremeno sačuvati sažetke, ali **nije pouzdana zamena za verzionisanu dokumentaciju** i ne podrazumeva automatsko čitanje GitHub datoteka u svakom razgovoru. Ovaj dokument ažurirati uz svaku verziju.
