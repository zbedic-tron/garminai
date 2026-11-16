# GarminAI Public v1.1.8 — Synthetic Delivery Resilience & Recovery

Datum: 2026-11-16. Diferencijalni ZIP se postavlja **preko postojećeg v1.1.7**; ne briši druge fajlove.

## Šta je novo?

- Nova D1 tabela `lab_recovery_v118` u već postojećoj Cloudflare bazi `garminai-synthetic-edge-v116`. Strogo fiktivni podaci: HMAC pseudonim, fiksni test event, digest, pokušaji, ACK. Ne dira `lab_bridge_v117` ni `lab_events_v116`.
- D1 Worker: `/_lab/recovery/{status,seed,claim,ack,inspect}`; `status` je bez ličnih podataka, a sve ostale operacije zahtevaju postojeći `BRIDGE_TOKEN`. Nema novog D1/Cloudflare naloga niti rotacije tajne.
- Dva nova MCP alata za potvrđenog OAuth korisnika: `run_synthetic_delivery_recovery` (mutacija, uz potvrdu i operator prekidač) i `get_synthetic_delivery_recovery_status` (read-only stanje za prijavljenog korisnika).
- Nova javna READ ONLY konfiguraciona ruta `/garmin/ingress/delivery-recovery`; nikad ne otkriva korisničke zapise niti proverava remote D1.
- Oporavak na ponovni poziv: ako Neon upis uspe, ali D1 ACK izostane, sledeći `RECOVER` ponavlja upis idempotentno i tek potom potvrđuje D1.
- NEMA stvarnog Garmin push-a, preuzimanja Garmin aktivnosti, AI deljenja, automatizovanog polling-a, background cron-a ni realnog prekidanja Render/Neon servisa.

## Obavezni uslovi

Korisnik je već uspešno testirao v1.1.7 D1→Neon→ACK sintetički tok. Render je na `1.1.7`; Cloudflare je postojeći Workers Free nalog sa D1 laboratorijom i `BRIDGE_TOKEN`. Ne treba ponavljati Garmin OAuth, Neon migracije 001–005 niti menjati `DATABASE_URL`.

**0 € novih troškova**: koriste se samo postojeći Free resursi. Ako Cloudflare ponudi Paid/naplatu, STOP.

## 1. GitHub / Render

Raspakuj ZIP i kopiraj **sadržaj** njegovog foldera `public/` u **isti** `public/` direktorijum postojećeg repozitorijuma; overwrite samo fajlove koji su već u ZIP-u. Commit i proveri Render deploy.

- `https://garminai-public-demo.onrender.com/healthz` → `version:1.1.8`.
- `https://garminai-public-demo.onrender.com/garmin/ingress/readiness` → `BLOCKED` (očekivano).
- `https://garminai-public-demo.onrender.com/garmin/ingress/delivery-recovery` → `mode:SYNTHETIC_DELIVERY_RECOVERY_OPT_IN`, `production_readiness:BLOCKED`, `operator_enabled:false` dok ne odobriš test.

## 2. Cloudflare — samo postojeća D1 baza, bez tajni

ZIP sačuvaj u `D:\Downloads`, pa u Windows PowerShell-u:

```powershell
$folder = 'D:\Downloads\GarminAI-Public-v1.1.6'
$zip = 'D:\Downloads\GarminAI-Public-v1.1.8-Synthetic-Delivery-Recovery-Delta.zip'
Expand-Archive -LiteralPath $zip -DestinationPath $folder -Force
Set-Location "$folder\public\edge_lab_v116"
if (-not (Test-Path '.\wrangler.toml')) { throw 'STOP: postojeća D1 konfiguracija nedostaje.' }
powershell.exe -NoProfile -ExecutionPolicy Bypass -File '.\Install-Recovery-V118.ps1' -Deploy
```

Skripta traži `FREE` i `SYNTHETIC`, koristi **postojeći** `wrangler.toml` i `BRIDGE_TOKEN`; primenjuje idempotentnu **D1 (SQLite) šemu** i deployuje ažurirani sintetički Worker. Tajna se ne štampa, ne šalje u ovaj razgovor, ne upisuje u GitHub. Nije potrebna nova `LAB_TOKEN` ili `BRIDGE_TOKEN` vrednost. Ne pokretati `Setup-Cloudflare-Free.ps1` niti `Install-Bridge-V117.ps1` ponovo.

Posle skripte proveri `https://garminai-synthetic-edge-v116.zbedic.workers.dev/_lab/recovery/status`: `version:1.1.8`, `recovery_enabled:true`, `real_garmin_push_enabled:false`.

## 3. Render staging prekidač, MCP test

U Render Environment postojeće `GARMINAI_EDGE_BRIDGE_URL` i `GARMINAI_EDGE_BRIDGE_TOKEN` ostaju kako jesu. Ako je stari `GARMINAI_EDGE_BRIDGE_STAGING_ENABLED=1`, vrati ga na `0`. Proveri da je i `GARMINAI_PUSH_REHEARSAL_STAGING_ENABLED=0`.

Za **ovaj jedan kontrolisani test** dodaj `GARMINAI_EDGE_RECOVERY_STAGING_ENABLED=1` i sačuvaj, sačekaj uspešan Render deploy. U ChatGPT GarminAI MCP podešavanjima **Refresh tools** (sada 10 alata).

Zatim pozovi u ChatGPT-u redom:

1. `run_synthetic_delivery_recovery(confirmation="RUN_SYNTHETIC_DELIVERY_RECOVERY", scenario="SIMULATE_RENDER_DELAY")` → `SIMULATED_RENDER_DELAY_D1_PENDING`; nema Neon upisa.
2. `run_synthetic_delivery_recovery(confirmation="RUN_SYNTHETIC_DELIVERY_RECOVERY", scenario="SIMULATE_NEON_UNAVAILABLE")` → `SIMULATED_NEON_UNAVAILABLE_D1_PENDING`; nema Neon upisa.
3. `run_synthetic_delivery_recovery(confirmation="RUN_SYNTHETIC_DELIVERY_RECOVERY", scenario="SIMULATE_D1_ACK_UNAVAILABLE")` → `SIMULATED_D1_ACK_UNAVAILABLE_NEON_COMMITTED`; Neon je zapisao/već imao **jedan fiktivni v118 događaj**, D1 je namerno ostao PENDING.
4. `run_synthetic_delivery_recovery(confirmation="RUN_SYNTHETIC_DELIVERY_RECOVERY", scenario="RECOVER")` → `PASS`, `neon_duplicate_prevented:true`, `d1_acknowledged:true`.
5. `get_synthetic_delivery_recovery_status()` → `ACKED_SYNTHETIC`, brojač pokušaja, **bez identiteta ili payload-a**.

Ako se pojavi `EDGE_RECOVERY_NOT_READY`, `NEON_WRITE_NOT_CONFIRMED` ili `NEON_COMMITTED_D1_ACK_PENDING`, sačuvaj bezbedni status, ne šalji tajne. Ne pokreći ponovo Cloudflare instalaciju. Već potvrđeni događaj može bezbedno da se ponovi sa `scenario="RECOVER"` kada je problem otklonjen.

**Odmah po završetku testova** vrati `GARMINAI_EDGE_RECOVERY_STAGING_ENABLED=0` i sačuvaj Render deploy. Read-only MCP status ostaje dostupan autentifikovanom korisniku ako su postojeći token i URL podešeni; mutacije su zaključane.

## 4. Granice bezbednosti i validnosti

- Ove simulacije **ne izazivaju stvarni Render cold start ni Neon outage**; cilj je proveriti obradu PENDING stanja, izostalog ACK-a i idempotentan oporavak već sačuvanih sintetičkih podataka.
- Nema automatske isporuke dok Render spava. Oporavak je **ručni MCP poziv**; nema garancije roka obrade niti beskonačne retencije.
- Cloudflare Workers Free/D1 stvarni kapacitet i dostupnost nisu SLA za Garmin. Proizvodni webhook je i dalje `503`, a `/garmin/ingress/readiness` ostaje `BLOCKED`.
- Garmin partner dokumentacija i AI ugovorna ograničenja ostaju poverljivi i van GitHub-a. NEMA korišćenja stvarnih ili izvedenih Garmin podataka dok se bezbednost izvora i ugovorne dozvole ne razjasne.
- D1 SQL `schema_recovery_v118.sql` je za **Cloudflare D1**, **ne** za Neon SQL Editor. Neon nema nove migracije; RLS prava `garminai_app` ostaju SELECT/INSERT, bez UPDATE/DELETE.

## Provera u ovoj izradi

Lokalne testove treba razlikovati od live testova na korisnikovom Cloudflare/Render/Neon. Paket se predaje kao **spreman za instalaciju**, a realni sintetički E2E PASS tek treba da potvrdi korisnik.
