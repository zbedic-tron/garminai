# GarminAI Public v0.6.1 — bezbedna provera veze Render → Neon

Status: razvojni DEMO; nema Garmin OAuth prijave, korisnika ni stvarnih aktivnosti.

## Sta radi ovaj korak

- Pri startovanju Render servisa pokusava kratku READ ONLY sesiju preko DATABASE_URL.
- Potvrdjuje da je prijavljeni korisnik tacno `garminai_app`, da nema superuser/BYPASSRLS/CREATEROLE/CREATEDB, da postoje 4 tabele sa ENABLE + FORCE RLS, 4 politike i SELECT prava.
- Izvrsava samo citanje sistemskih metapodataka: bez citanja redova sa Garmin podacima, bez izmene podataka.
- Status upisuje iskljucivo u **Render Logs**: `GARMINAI_DB_CHECK: PASS (OK)` ili `FAIL (KOD)`.
- Nema javnog endpointa koji otkriva host, lozinku ili strukturu baze.
- Ako provera ne uspe, demo server i dalje radi; neuspeh ne znaci da je baza ostecena.
- `/integration/readiness` i dalje pokazuje `schema_initialized: NOT_CHECKED`, jer je taj endpoint samo konfiguraciona provera. Za stvarni rezultat gledaj Render Logs.

## Postavljanje na GitHub

1. Raspakuj ZIP. Sadrzaj `public/` prebaci u postojeci `public/` direktorijum na GitHub-u, uz zamenu promenjenih fajlova; nemoj napraviti `public/public/`.
2. `render.yaml` ostaje u korenu. HTML sajt i privatni Windows GarminAI ne diraj.
3. Render automatski pokrece deploy. `/healthz` mora prikazati `0.6.1`.
4. Render Dashboard → garminai-public-demo → Logs. Potrazi `GARMINAI_DB_CHECK:`. Salji samo taj red (bez drugih tajni).
5. `DATABASE_URL` ostaje u Render Environment, samo za `garminai_app`. Nema potrebe dodavati druge kljuceve.

Za ponavljanje dijagnostike moze se uraditi **Manual Deploy → Deploy latest commit** (samo ako je neophodno). Nema potrebe dodatno pokretati placene servise.

## Granice rezultata

`PASS` potvrdjuje samo da se Render povezao sa Neonom i da su ocekivane zastite prisutne. Ne znaci da su testirani stvarni webhook/push, produkcioni korisnicki identitet, cuvanje Garmin tokena, backup, prava na AI obradu ili 24/7 pouzdanost na Render Free. Ne koristiti prave korisnicke podatke jos.
