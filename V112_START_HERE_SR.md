# GarminAI Public v1.1.2 — START HERE (delta ZIP)

## Šta novo donosi?
- Samo mali broj novih i izmenjenih fajlova u odnosu na v1.1.1; ostali projekat na GitHub-u ostaje netaknut.
- Novi **`run_synthetic_push_rehearsal` MCP alat**: uz eksplicitni `RUN_SYNTHETIC_REHEARSAL` i Render operator opt-in, kod koristi već potvrđeni Neon korisnički identitet, proverava njegovu postojeću Garmin vezu **bez čitanja treninga** i pokušava da upiše **jednu jasno označenu fiktivnu aktivnost** u `garminai.garmin_push_inbox`. Ponavlja identičan zahtev da potvrdi da isti zapis ne nastaje dvaput.
- Fiktivni inbox zapis se **namerno trajno zadržava** (najviše jedan po korisniku), kako bi se stvarno proverio upis i idempotencija preko odvojenih DB transakcija. Ne prosleđuje se u `garminai.activities` ni u AI. U bilo kojoj budućoj obradi mora se ignorisati ID `GARMINAI_SYNTHETIC_V112`.
- Dodata projektna dokumentacija za **nastavak u novom threadu**, bez lozinki ili poverljivih Garmin materijala: `public/docs/PROJECT_CONTINUITY_SR.md`.

## Postavljanje (GitHub web, Render, Neon, ChatGPT)
1. Raspakuj ZIP; u GitHub-u kopiraj nove i izmenjene fajlove iz `public/` u postojeći `public/`; nemoj brisati ostale. `V112_START_HERE_SR.md` je lokalno uputstvo, ne Python kod.
2. Commit; Render deploy; proveri `/healthz` sa verzijom `1.1.2` i `/garmin/integration/status` sa `push_ingestion_enabled:false`, `mcp_real_garmin_data_enabled:false`, `verified_live_ingress_enabled:false`.
3. **Nije potrebna nova SQL migracija.** Neon `001`–`005` su već postavljene i RLS proveren.
4. Render Environment: **privremeno** dodaj `GARMINAI_PUSH_REHEARSAL_STAGING_ENABLED=1` i sačuvaj. Ovaj flag NE uključuje Garmin push, već isključivo fiktivni MCP DB test.
5. U ChatGPT-u otvori GarminAI MCP → Settings → Manage app → **Refresh tools**. Novi sedmi alat: `run_synthetic_push_rehearsal`.
6. Pošalji: „Pozovi `run_synthetic_push_rehearsal` sa `confirmation=RUN_SYNTHETIC_REHEARSAL`. Samo sintetički Neon test, nemoj čitati stvarne Garmin aktivnosti.“
7. Očekivano: `status: PASS`, `fixture: SYNTHETIC_ONLY`, `duplicate_prevented:true` i `real_activities_read:false`. U slučaju `STORAGE_NOT_READY`, `CHECK_FAILED`, `GARMIN_LINK_REQUIRED` stani i proveri konfiguraciju; ne menjaj bazu naslepo.
8. Opciona Neon SQL provera (privatni SQL Editor): `SELECT COUNT(*) AS synthetic_rows FROM garminai.garmin_push_inbox WHERE activity_id = 'GARMINAI_SYNTHETIC_V112';` Očekuje se 1 ako je samo jedan korisnik izvršio probu.
9. **Render Environment flag vrati na `0`** posle testa; nema potrebe da Garmin OAuth ponovo povezuješ niti da brišeš sintetički testni red.

## Ograničenja i rollback
- Ne uključuj ništa u Garmin API Tools → Endpoint Configuration. Javni `/garmin/push/*` mora ostati `503`.
- Nije test mrežne isporuke od Garmina, autentifikacije pošiljaoca, timeout/cold-start ponašanja, niti stvarnog pristupa treninzima. Ovo je verifikacija upisa sintetičke poruke preko autentifikovanog MCP i PostgreSQL aplikacione uloge, uz rezultate privatne baze.
- Čak i po rezultatu `PASS`, stvarni Garmin podaci **ne idu u ChatGPT**. Partner dokumentacija i ugovor ostaju poverljivi, posebno ograničenja AI korišćenja.
- Vraćanje: vratiti izmenjene Python fajlove na v1.1.1 i ugasiti `GARMINAI_PUSH_REHEARSAL_STAGING_ENABLED`. Ne brisati Garmin OAuth vezu ili postojeće podatke. Eventualno uklanjanje sintetičkog reda kroz Neon kao vlasnik šeme samo ako je zaista potrebno, posle provere podataka.
- 0 € dodatnih troškova, bez novih servisa ili javne objave.

## Kako nastaviti u novom ChatGPT razgovoru
Priloži `public/docs/PROJECT_CONTINUITY_SR.md`, ili ga nalepi kao tekst. Počni: „Nastavljamo GarminAI Public iz projektnog dosijea. Trenutna verzija je v1.1.2. Prvo proveri aktuelno stanje, ne ponavljaj prethodno završene migracije. Diferencijalni ZIP-ovi ispod 100 fajlova i politika 0 € ostaju obavezni.“
