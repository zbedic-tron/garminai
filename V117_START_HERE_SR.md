# GarminAI Public v1.1.7 — D1 → Neon, ISKLJUČIVO SINTETIČKI

**Ishod:** diferencijalni ZIP preko postojećeg GitHub/Render v1.1.6 i već postavljenog Cloudflare Worker-a v1.1.6.4. Ova verzija još **nije** instalirana na korisnikovim servisima. Operativna provera je sledeći korak. Nikad ne uključivati Garmin Endpoint Configuration.

## 1) GitHub i Render

1. Raspakuj ZIP. Kopiraj **sadržaj `public/` u postojeći GitHub `public/`**, uz očuvanje putanja. Nije kompletan repo. `wrangler.toml` i ikakve tajne nisu u ZIP-u.
2. GitHub Commit → Render automatski deploy.
3. Proveri `/healthz` → `1.1.7`; `/garmin/ingress/readiness` → `BLOCKED`; `/garmin/ingress/edge-to-neon` → `SYNTHETIC_EDGE_TO_NEON_OPT_IN` i `operator_enabled: false`.
4. Za sada ne diraj `GARMINAI_PUSH_REHEARSAL_STAGING_ENABLED=0`.

## 2) Cloudflare — već postojeći besplatni Worker i D1

Za Cloudflare instalaciju prvo raspakuj isti ZIP i u lokalni **postojeći** folder `D:\Downloads\GarminAI-Public-v1.1.6` (ne briši `wrangler.toml` i ne vraćaj stari Setup skript preko 1.1.6.4).

U Windows PowerShell-u pokreni:

```powershell
Set-Location 'D:\Downloads\GarminAI-Public-v1.1.6\public\edge_lab_v116'
Test-Path .\wrangler.toml
powershell.exe -NoProfile -ExecutionPolicy Bypass -File '.\Install-Bridge-V117.ps1' -Deploy
```

Ako `Test-Path` nije `True`, **stani**. Skripta će pitati `FREE` i `SYNTHETIC`, proveriće postojeći D1, izvršiti **samo `schema_bridge_v117.sql`**, ponovo objaviti isti Worker, zatim dodati NOVU tajnu **`BRIDGE_TOKEN`** na Cloudflare, nezavisnu od postojećeg `LAB_TOKEN`. Nova tajna će biti kopirana **samo u Windows clipboard**, bez prikazivanja u terminalu, fajlu ili ChatGPT-u. **Ne ponavljaj skriptu** nakon uspeha, jer bi rotirala Bridge tajnu; D1 baza se ne kreira ponovo.

Ako bilo koji korak traži plaćeni plan ili karticu, zaustavi se.

## 3) Render Environment — tri promenljive za PRIVREMENI test

- `GARMINAI_EDGE_BRIDGE_URL` = `https://garminai-synthetic-edge-v116.zbedic.workers.dev`
- `GARMINAI_EDGE_BRIDGE_TOKEN` = **PASTE (Ctrl+V)** iz Windows clipboard-a nakon uspešne Cloudflare instalacije; **nikad ne štampati ili slati u chat**.
- `GARMINAI_EDGE_BRIDGE_STAGING_ENABLED` = `1` **samo za kontrolisani sintetički test**.

Render će primeniti ove promene i ponovo pokrenuti servis. Ne menjati `DATABASE_URL`, Garmin OAuth Client ID/secret, Neon korisnika, niti izvorne Garmin API Tools postavke.

## 4) ChatGPT — 8. MCP alat

GarminAI MCP → Settings → Manage app → Refresh tools. Novi alat: `run_synthetic_edge_to_neon_rehearsal`.

Pošalji: „Koristi GarminAI MCP i pozovi `run_synthetic_edge_to_neon_rehearsal` sa `confirmation="RUN_SYNTHETIC_EDGE_TO_NEON"`. Testiraj samo jedan sintetički Cloudflare D1 → Neon upis, duplikat i potvrdu. Ne čitaj stvarne Garmin aktivnosti.“

Očekivani odgovor: `status: PASS`, `d1_durable_receipt:true`, `neon_duplicate_prevented:true`, `d1_acknowledged:true`. Ako je `NEON_COMMITTED_EDGE_ACK_PENDING`, Neon može biti uspešno upisan ali Cloudflare ACK nije potvrđen; isti MCP alat može se ponoviti nakon utvrđivanja greške. **Ne brisati tabele ili raditi migracije naslepo.**

D1 zadržava najviše jedan sintetički bridge zapis po autentifikovanom Neon subjektu; Neon takođe najviše jedan odgovarajući fiktivni inbox red po subjektu. Ne šalje se Garmin ID niti stvarni trening na Cloudflare.

## 5) Zaključavanje posle testa

1. Render `GARMINAI_EDGE_BRIDGE_STAGING_ENABLED=0`, Save and deploy.
2. Izbriši tajnu iz Windows clipboard-a lokalno: `Set-Clipboard -Value ' '`.
3. `/garmin/ingress/edge-to-neon` treba da pokaže `operator_enabled:false`.
4. `/garmin/ingress/readiness` ostaje `BLOCKED`; svi javni Garmin `/garmin/push/*` i dalje su `503`.

## Bezbednosne granice

- Uobičajeni Garmin OAuth povezani nalog i demo MCP zadržavaju postojeći status. Ovo je samo laboratorijski tok sa izmišljenim konstantama.
- Render **povlači** pojedinačni potpisani/pseudonimizovani D1 testni zapis samo kroz MCP sa potvrđenim Neon subjektom. Nema javne Render POST rute za bridge.
- D1 potvrda se šalje tek **nakon uspešno završene Neon transakcije**. Ponovni pokušaj je idempotentan.
- Ovo NE dokazuje dozvoljenost Garmin podataka za Cloudflare ili ChatGPT, verifikovanu autentifikaciju Garmin pošiljaoca, ispunjenost 30s push SLA ili produkcionu spremnost. Ne stavljati Worker URL u Garmin Developer Portal.
- 0 € dodatnih troškova; samo postojeći Workers Free + Render Free + Neon Free. Nema nove Neon SQL migracije.

Čuvaj `public/docs/PROJECT_CONTINUITY_SR.md` kao trajni dosije; odatle se može nastaviti u novom razgovoru.
