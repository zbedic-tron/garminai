# GarminAI Public v1.1.4 — procena spremnosti Garmin push prijema

**Status: PRIPREMA / BLOKIRANO — NIJE produkcioni push prijem.** Ova verzija uvodi read-only izveštaj i dodatne regresione testove. Ne menja Garmin OAuth povezanost, MCP alatke, migracije ni Render ključeve.

## Provere i nalazi

- `GET /garmin/ingress/readiness` prikazuje isključivo bezbedne booleane: izvor zahteva nije pouzdano potvrđen, nema zagarantovanog vremena odgovora, a live push je i dalje isključen. **Nije mrežni probe ni potvrda da je Garmin povezan.**
- Render Free web servis se uspavljuje kad nema saobraćaja; vraćanje iz mirovanja nije vremenski garantovano. Ne koristimo veštački keep-alive, spoljašnje raspoređivače ni plaćene servise kao zamenu za SLA.
- Render Free za web servise ne pruža upravljana inbound IP pravila. Obični `X-Forwarded-For` / slična zaglavlja nisu nezavisna autentifikacija izvora; čak ni poklapanje IP sa referentnim opsegom nije dokaz autentičnosti. U repozitorijumu nema poverljivih Garmin IP lista.
- Javni `POST /garmin/push/*` ostaje `503` za sve tipove poruka, čak i uz falsifikovana IP zaglavlja ili operator flag; test ne šalje podatke Neonu.
- Garminov servis dostave očekuje odgovor unutar svog vremenskog ograničenja, a Render Free cold-start može trajati duže. Nije dovoljno osloniti se na retry.
- Sintetički Neon test je **prijavljen kao PASS nakon v1.1.3** od korisnika; ova read-only ruta ne pokreće test i ne proverava dva stvarna korisnika.
- Ugovorne obaveze iz Garmin Developer sporazuma u vezi sa eksternim AI sistemima, infrastrukturom, troškovima i korišćenjem podataka ostaju otvorene. Ni realne ni izvedene Garmin aktivnosti se ne prosleđuju ChatGPT-u.

## GitHub / Render / kontrola

1. Prekopiraj **samo** fajlove iz diferencijalnog ZIP-a na odgovarajuće GitHub putanje. Ne briši ostale fajlove.
2. Commit i Render deployment; `/healthz` mora prijaviti `1.1.4`.
3. Otvori `https://garminai-public-demo.onrender.com/garmin/ingress/readiness`; očekuj `readiness: BLOCKED`, `live_garmin_push_enabled: false`, `trusted_source_provenance_verified: false`.
4. `/garmin/integration/status` treba da prijavi isključene realni push i AI pristup.
5. Ako je sintetički test završen, proveri da je `GARMINAI_PUSH_REHEARSAL_STAGING_ENABLED=0` na Renderu; ne dodavati nove tajne ili SQL migracije.
6. **Ne uključuj** Garmin Endpoint Configuration niti javni push, ne menjaj OAuth, `DATABASE_URL` ili PostgreSQL prava.

## Otvoreno za naredni rad (bez novih troškova)

- Pronaći proverljiv **besplatan, dopušten** način prijema partner webhooka: pouzdan dokaz izvora plus vremenski pouzdan HTTP ACK i trajno skladištenje. Samo pretpostavljena originalna IP adresa nije dovoljna.
- Uskladiti obradu Garmin deregistration / permissions / brisanja, privolu i pravno dozvoljenu dalju upotrebu podataka.
- Pre bilo kakvog rešenja koje može stvoriti troškove: eksplicitna potvrda korisnika, nikad automatska nadogradnja.

**Rollback:** vrati v1.1.3 kod; nema migracije niti promena tajnih ključeva.

**Tehnički izvori (javni):** https://render.com/docs/free , https://render.com/docs/inbound-ip-rules . Poverljivi Garmin ugovor i Activity API PDF nisu u GitHub repozitorijumu.
