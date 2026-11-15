# GarminAI Public v1.0.2 — CSP Garmin redirect HOTFIX

**Diferencijalni ZIP** u odnosu na v1.0.1. Nema SQL migracija, novih API ključeva, novih Render Environment promenljivih ni promena MCP alata.

## Problem

Na stranici "Poveži Garmin Connect", klik "Nastavi na Garmin" može ostati bez vidljivog efekta u Chrome-u. `/garmin/oauth/authorize` ispravno vraća HTTP 303 ka `https://connect.garmin.com`, ali CSP `form-action 'self'` na prethodnoj strani može blokirati cross-origin odredište nakon form submit-a.

## Ispravka

- Samo za HTML stranicu za potvrdu dodato je `form-action 'self' https://connect.garmin.com`.
- Ostale stranice zadržavaju strogi `form-action 'self'`.
- `script-src 'none'`, `frame-ancestors 'none'`, cookies, PKCE, jednokratni state i RLS nisu menjani.
- `GARMINAI_GARMIN_LINK_STAGING_ENABLED` ostaje na postojećoj vrednosti; push prijem i deljenje podataka sa ChatGPT-om ostaju ISKLJUČENI.

## Instalacija kroz GitHub/Render

1. Raspakuj ZIP; prenesi samo sadržaj njegovog `public/` foldera u postojeći `public/` folder u GitHub-u. Ne briši druge fajlove.
2. Commit; proveri Render deploy i `/healthz` (`version: 1.0.2`).
3. Osveži staru karticu za povezivanje i zatraži **novi** privatni link komandom `get_garmin_connection_link` (link važi 10 min).
4. Klikni `Nastavi na Garmin` i očekuj Garmin ekran autorizacije. Ne šalji link, `state`, `code`, tokene ili ključeve u ChatGPT.
5. Ako i dalje ne radi: F12 -> Network, uključi Preserve log, pa posmatraj samo metod, putanju i status. Očekivano: `POST /garmin/oauth/authorize` -> `303`, sledeći zahtev -> `connect.garmin.com`. U Console proveri ima li CSP greške. Ne kopiraj pune URL-ove.
6. Nakon završene autorizacije pozovi samo `get_garmin_connection_status`. Bez čitanja aktivnosti.

**Rollback:** vrati originalne datoteke iz v1.0.1 delta ZIP-a koje su promenjene u ovom paketu ili odgovarajući prethodni GitHub commit. Ne menjaj SQL, kredencijale ili postojeći plugin.

**Granice potvrde:** testovi proveravaju generisanu CSP politiku i HTTP 303 u lokalnom ASGI klijentu. Stvarna Chrome/Render/Garmin autorizacija zahteva proveru uživo. Politika dodatnih troškova: 0 €.
