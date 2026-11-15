# GarminAI Public v1.1.3 — Neon synthetic rehearsal privilege hotfix

## Šta je ispravljeno
U v1.1.2 `run_synthetic_push_rehearsal` vraćao je `STORAGE_NOT_READY`. Inspekcijom koda identifikovane su dve `SELECT ... FOR UPDATE` naredbe u `garmin_push_inbox_v111.py`. PostgreSQL zahteva UPDATE pravo za takve row-locking klauzule, a `garminai_app` namerno ima samo SELECT/INSERT. To je najverovatniji uzrok — produkcioni PostgreSQL traceback još nije pregledan.

v1.1.3 koristi obične RLS-scoped SELECT upite za proveru vlasništva i sadržaja. Atomicnost upisa/idempotencija ostaje oslonjena na PK `(subject, activity_id)` i `INSERT ... ON CONFLICT DO NOTHING`; čitava transakcija se poništava pri grešci. Nije omogućena live Garmin ingest ruta niti prošireno pravo korisnika. Ovo je **sintetički** test; race sa disconnection i dalje zahteva zasebnu proveru pre bilo kakvog produkcionog push-a.

## Instalacija kroz GitHub web i Render
1. Raspakuj diferencijalni ZIP. Prebaci samo izmenjene fajlove iz `public/` u istoimene putanje u GitHub-u, bez brisanja ostalih fajlova. `V113_START_HERE_SR.md` je uputstvo.
2. Commit; Render deploy; `https://garminai-public-demo.onrender.com/healthz` treba da pokazuje `version: 1.1.3`.
3. **Ne pokreći nikakvu novu SQL migraciju. Ne radi GRANT UPDATE, ne menjaj RLS, DATABASE_URL, Garmin ključeve ili callback.**
4. Za jedno ponavljanje testa privremeno zadrži/postavi `GARMINAI_PUSH_REHEARSAL_STAGING_ENABLED=1` u Render Environment. Ako je već `1`, ne moraš menjati.
5. Nakon deploymenta pozovi u privatnom ChatGPT GarminAI MCP: `run_synthetic_push_rehearsal` sa `confirmation="RUN_SYNTHETIC_REHEARSAL"`. Osvežavanje MCP alata uglavnom nije potrebno: ime i parametri alata nisu promenjeni.
6. Očekivano: `status: PASS`, `fixture: SYNTHETIC_ONLY`, `duplicate_prevented: true`, `real_activities_read: false`. Ako rezultat odstupi, pošalji samo bezbedan status, ne tajne, i zaustavi se.
7. Opcionalna provera kroz vlasnički Neon SQL Editor, po potrebi: `SELECT count(*) FROM garminai.garmin_push_inbox WHERE activity_id='GARMINAI_SYNTHETIC_V112';` Očekuje se jedan red ako je samo jedan verifikovani nalog testiran; test ne pravi stvarni Garmin trening.
8. Na kraju vrati `GARMINAI_PUSH_REHEARSAL_STAGING_ENABLED=0` i proveri ponovni deploy.

## Bezbednosne granice
- Javni Garmin `/garmin/push/*` i dalje je zaključan (`503`); ništa ne uključivati u Garmin API Tools Endpoint Configuration.
- Nema čitanja Garmin aktivnosti i nema slanja stvarnih ni izvedenih Garmin podataka u ChatGPT.
- Postojeći Garmin OAuth nalog ostaje povezan; `get_garmin_connection_status` je odvojena provera od demo `get_sync_status`.
- Operator opt-in + izričita potvrda i dalje su obavezni; sintetički inbox red (najviše jedan po subjectu) može ostati u bazi.
- Samo besplatni planovi i alati, 0 € dodatnih troškova. Diferencijalni GitHub ZIP ispod 100 fajlova.

## Ako i dalje dobijemo `STORAGE_NOT_READY`
Mogući su drugi razlozi koji nisu potvrđeni, npr. nedostajuće privilegije na vezi, razlika između baza/grana ili nepoklopljen identitet. Ne dodavati privilegije naslepo. Prvo proveriti status Render deploymenta, aktuelni DB-check i da uloga/šema odgovaraju postavljenoj migraciji; zatim dodati strogo redigovanu server-side dijagnostiku.
