# GarminAI Public v1.1.9 — Sintetički Delivery Reliability / Observability

## Svrha
Privatna vidljivost u već potvrđenu D1 v1.1.8 recovery poruku i opciono **jedno ručno** ponavljanje neisporučenog događaja. Ne prikuplja stvarne Garmin treninge.

## Trenutni potvrđeni status
16.11.2026: prethodni ChatGPT MCP testovi v1.1.8 završeni `PASS` 4/4, završni D1 `ACKED_SYNTHETIC`, broj claim pokušaja 3, a recovery operator flag vraćen na 0 (prema korisniku). Naš novi kod nije još instaliran na Render do korisničke potvrde.

## Novi MCP alati

### get_synthetic_delivery_observability
- Uvek **read-only**, zahteva verifikovani Neon OAuth principal; koristi isključivo postojeći `/_lab/recovery/inspect` kroz postojećeg HTTPS Worker klijenta i postojeći `BRIDGE_TOKEN` koji ostaje tajna na Renderu.
- Prikazuje: `delivery_state`, D1 ACK, `d1_claim_attempts`, `remaining_manual_attempts`, `attention`, operator bool. Nema fizičkog ID-a, subject-a, poruke, tokena, Garmin treninga ili loga mrežnih grešaka.
- `last_failure_code=NOT_RECORDED_IN_V118_SCHEMA` i `historical_latency_available=false` su iskrena ograničenja (v1.1.8 šema ne čuva uzrok greške ni trajanje pojedinačnih koraka).
- Može pokazati `NOT_STARTED` ili `OBSERVABILITY_UNAVAILABLE`, što nije dokaz da D1 nema podatke ili da je Neon prazan. Ne upituje Neon nezavisno.

### run_synthetic_delivery_safe_retry
- **Ne koristiti ako je već ACKED.** Jedina dozvoljena radnja je `RECOVER` nad postojećim PENDING događajem. Ne pravi novi event.
- Zahteva `GARMINAI_EDGE_RELIABILITY_STAGING_ENABLED=1` u Render Environment *i* `confirmation="RUN_SYNTHETIC_SAFE_RETRY"` u autentifikovanom MCP pozivu. Flag se odmah posle eventualnog operator-odobrenog testa vraća na 0.
- Pre upisa proverava da je događaj PENDING i da je broj D1 claim pokušaja strogo manji od šest. Ograničenje je **aplikaciono** i nije garantovana atomska globalna kvota kod istovremenih poziva — samo laboratory safety.
- Bezbedno koristi već testiran v1.1.8 `RECOVER` transakcioni tok. Ako je Neon upis uspeo, a ACK zakasnio, novi poziv koristi postojeći `INSERT ... ON CONFLICT` i pokušava potvrdu bez dupliranja; kod ne dodeljuje UPDATE/DELETE prava `garminai_app`.
- Potvrđeni ACK se više ne dira. Poziv na već ACKED stanje vraća `ALREADY_ACKNOWLEDGED` bez claim-a/Neon upisa.
- U slučaju nepoznatog stanja/greške: fail closed, nema obećanog uspeha.

## Instalacija
Nema instalacije na Cloudflare-u niti nove D1 ili Neon SQL migracije; samo GitHub/Render delta i MCP Refresh tools.
1. Sadržaj delta ZIP-a preko *postojećeg* GitHub `public/` foldera, bez brisanja postojećih fajlova; commit i Render deploy.
2. `https://garminai-public-demo.onrender.com/healthz` -> 1.1.9.
3. `https://garminai-public-demo.onrender.com/garmin/ingress/delivery-observability` -> `operator_manual_retry_enabled=false`, `production_readiness=BLOCKED`.
4. ChatGPT GarminAI MCP → Manage app → Refresh tools → 12 alata.
5. Proveriti read-only alat `get_synthetic_delivery_observability` (bez operator flag-a). Očekujemo ACKED v1.1.8 record, 3 pokušaja ako ga niko nije menjao.
6. Ako nema novog problema, završiti bez novih poziva i ostaviti sve flag-ove isključene.

## Ograničenja
Nema automatskog retry scheduler-a, background rada, retention politike ni audit istorije grešaka. Nema pouzdane produkcione Garmin sender autentifikacije, rešenog 30s garmin push SLA, ni ugovorne dozvole za Cloudflare/AI obradu stvarnih podataka. Javni Garmin `/garmin/push/*` vraća 503. Bez novih plaćenih funkcija, bez stvarnih aktivnosti, bez tajni u GitHub-u ili ChatGPT-u.
