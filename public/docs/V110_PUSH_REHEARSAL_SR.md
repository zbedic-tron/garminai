# GarminAI Public v1.1.0 — Garmin Activity Push, bezbedna trajna proba (DELTA)

**Ovo je priprema prijema Activity API događaja. Nije uključeno primanje stvarnih Garmin podataka.**

## Šta dodaje

- `PostgresPushRehearsalStore`: transakcioni, tenant-scoped, idempotentni upis **sintetičkih** Activity JSON sažetaka u postojeću tabelu `garminai.activities` i novu tabelu `garminai.garmin_push_receipts`.
- RLS + FORCE RLS, `garminai_app` i stroga verifikacija ranije povezane Garmin veze za konkretnog Neon korisnika.
- Odbijanje tuđeg Garmin korisničkog ID-a, nepotpunih/izmenjenih batch objekata i konfliktnih ponovljenih ID-eva. Potpuni rollback pri grešci.
- Iz JSON-a se zadržava samo mali dozvoljeni podskup: vrsta aktivnosti, početak, trajanje i distanca. `userAccessToken`, lokacija i ostali neodobreni podaci se ne čuvaju.
- Zaštićena SQL migracija `004_garmin_activity_push_rehearsal.sql`, statusni prikaz i offline testovi.
- Svi javni `/garmin/push/*` endpointovi **ostaju zaključani (`503`)**, a `get_activities` u ChatGPT-u i dalje prikazuje **izmišljene** podatke.

## Instalacija (GitHub bez limita 100 fajlova)

1. Preduslov: na Renderu je uspešna v1.0.3 i Garmin OAuth nalog je već povezan.
2. Raspakuj ovaj **diferencijalni** ZIP. Kopiraj sadržaj `public/` preko istoimenih datoteka u GitHub-u. Ne briši druge fajlove.
3. Commit i Render deploy. Proveri `/healthz` sa `version = 1.1.0`.
4. Neon Console → Primary / `neondb` (ili grana koju stvarno koristi Render) → SQL Editor. Kao vlasnik šeme pokreni sadržaj `public/sql/004_garmin_activity_push_rehearsal.sql` jednom. Nije potrebna nova baza ni novi server.
5. Proveri `GARMINAI_DB_CHECK: PASS (OK)` u Render Logs, nakon restartovanja servisa. Ako je FAIL, ne otvaraj push destinacije u Garmin Portalu.
6. Proveri `/garmin/integration/status`: `version=1.1.0`, `push_ingestion_enabled=false`, `mcp_real_garmin_data_enabled=false`, `garmin_sender_authentication_verified=false`.
7. `/garmin/push/activities` i ostali push POST endpointovi moraju da odbiju realne zahteve. Ne registruj ih kao Garmin Endpoint Configuration destinacije.

## SQL provera nakon migracije

```sql
SELECT c.relname AS table_name, c.relrowsecurity AS rls_enabled,
       c.relforcerowsecurity AS force_rls,
       has_table_privilege('garminai_app', c.oid, 'SELECT') AS can_select,
       has_table_privilege('garminai_app', c.oid, 'INSERT') AS can_insert,
       has_table_privilege('garminai_app', c.oid, 'UPDATE') AS can_update
FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
WHERE n.nspname='garminai' AND c.relname='garmin_push_receipts';
```

Očekivano: **jedan red**, `t, t, t, t, f` (RLS, FORCE RLS, SELECT, INSERT, UPDATE).

## Testovi (bez stvarnih Garmin aktivnosti)

```bash
cd public
python -m unittest discover -s tests -v
node tests/js/test_login_flow.cjs tests/js/google_login_v0843.js
node tests/js/test_oauth_ui_v086.cjs tests/js/oauth_ui_v086.js
node tests/js/test_oauth_e2e_v087.cjs tests/js/oauth_e2e_v087.js
node tests/js/test_chatgpt_oauth_v090.cjs tests/js/oauth_ui_v086.js
```

Lokalno izvršeno: 163 Python testa i ukupno 63 Node browser simulacije. Testi koriste simulirane identitete, podatke i lažnu bazu; stvarni PostgreSQL upis tek treba proveriti u kontrolisanom integracionom testu, kada je pravno/bezbednosno dozvoljen.

## Šta je BLOKIRANO

- Autentifikacija i pouzdana identifikacija Garmin push pošiljaoca još nisu utvrđene prema privatnoj partner dokumentaciji. `userId` iz JSON-a, HTTPS ili nepoznata header vrednost **nisu dokaz porekla**.
- Nema javnog live ingestion prekidača u ovom paketu. Nemoj dodavati `GARMINAI_GARMIN_PUSH_ENABLED=1`; ne može zaobići zaključane rute.
- Ne treba uključivati `Activity Details`, `Activity Files`, `MoveIQ`, `Deregistrations` ili `User Permissions Change` bez njihove dokumentovane zaštite i odvojene validacije.
- Stvarni Garmin podaci ne smeju se slati eksternom AI pružaocu dok se ne provere Garminovi uslovi i ne pribavi posebna informisana saglasnost. Garmin AI pristup u ChatGPT-u ostaje OFF.
- Starter nema istorijski backfill ni Enterprise Ping/Pull. Ne koristi druge, neregistrovane Garmin API tokove.

## Dalje

U Garmin API Tools (sa postojećim kredencijalima) pregledati **Partner Verification**, Endpoint Configuration i zahtev Garminova API tima za auth push pošiljaoca i testno slanje. Podatke iz poverljive dokumentacije ne objavljivati javno niti unositi tajne u chat. Tek posle potvrde mehanizma možemo implementirati live prijem i pokazati stvarni HTTP 2xx test.

## Rollback

Vrati samo izmenjene `.py` fajlove na v1.0.3, a novu SQL tabelu možeš ostaviti **praznu**. Ne briši nijednu tabelu ako su u njoj podaci. Garmin OAuth i prethodna povezivanja nisu menjani. Bez dodatnih usluga ili plaćenih planova; pravilo 0 € ostaje.
