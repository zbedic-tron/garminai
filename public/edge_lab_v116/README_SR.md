# GarminAI v1.1.6 — Cloudflare Free sintetička laboratorija

**Bez Garmin API-ja, bez stvarnih Garmin podataka, bez AI-a.** Ovo nije produkcioni webhook, nije verifikovana autentifikacija Garmin pošiljaoca i nije povezano sa Renderom ili Neonom. Worker URL **nikad ne unositi u Garmin Endpoint Configuration**.

## Potrebno

1. Cloudflare nalog na **Workers Free** (proveriti da nije uključen Workers Paid ili drugi plaćeni servis).
2. Windows računar sa Node.js 20+ i PowerShell 5.1 ili 7; internet za preuzimanje besplatnog Wrangler CLI-ja.
3. Izvorni paket u folderu `public/edge_lab_v116`. Nije potrebno ni najmanje menjati postojeće Garmin/Render/Neon parametre.

## Koraci (PowerShell)

Pokrenuti PowerShell u folderu **`public/edge_lab_v116`** i izvršiti:

```powershell
node --version
npx --yes wrangler --version
powershell -NoProfile -ExecutionPolicy Bypass -File .\Setup-Cloudflare-Free.ps1 -Deploy
```

Skripta traži eksplicitnu potvrdu `FREE`, otvara Cloudflare prijavu, kreira **novu odvojenu D1 bazu**, primenjuje `schema.sql` na D1 (`--remote`), postavlja Worker i generiše nasumičnu tajnu u memoriji. Sekret `LAB_TOKEN` se čuva preko `wrangler secret put`; u GitHub se ne šalje. Na kraju testira `200`, ponovljeni `200`, konflikt `409` i ispisuje latenciju. Koristi isključivo `SYNTHETIC_...` ID.

**VAŽNO:** ovo kreira javno dostupan Cloudflare Worker URL, ali POST upis zahteva snažnu tajnu, unapred definisan JSON format i sintetičke ID-eve. Javni `GET /_lab/status` pokazuje samo bezbednu dijagnostiku. Pošto ne postoji Garmin sender auth, ne koristiti za stvarni push.

Skripta pravi lokalni `wrangler.toml` sa identifikatorom nove D1 baze. Nije tajna, ali je izostavljen iz GitHub delta ZIP-a da ne dođe do zabune između naloga. Ako skripta stane posle kreiranja baze, **ne pokretati je odmah ponovo** jer bi mogla pokušati kreiranje baze istog naziva; sačuvati poruku o grešci bez tokena i prvo proveriti Cloudflare dashboard.

## Provera upisa u stvarnu D1 bazu

```powershell
npx --yes wrangler d1 execute garminai-synthetic-edge-v116 --remote --command 'SELECT COUNT(*) AS total FROM lab_events_v116;'
```

Pri prvom izvršavanju laboratorijskog testa očekujemo `total: 1`, pod uslovom da je baza bila prazna. Ako skriptu pokrenemo više puta i ranije postoji testni zapis, broj će biti veći, ali svaki ponovljeni zahtev sa istim event ID ne sme dodati još jedan.

Za ručno gašenje nakon testa: u Cloudflare Workers Dashboard → Worker → Settings → Variables and Secrets postaviti `LAB_SYNTHETIC_ONLY` na `0` ili ukloniti Worker. *Ne brisati D1 bazu bez prethodne provere šta sadrži.*

## Šta test dokazuje, a šta ne

- Dokazuje stvarni HTTPS pristup Cloudflare Worker-u i D1 upis na **tvom Free nalogu**, kada ga ti izvršiš i pošalješ rezultate.
- Primer merenja latencije je indikativan za tu testnu mrežu, **nije garancija SLA/raspoloživosti**.
- Nije proveren realan Garmin webhook, IP izvori, D1->Neon repliciranje, GDPR/DPA, autorizacija provajdera, brisanje, oporavak od kvara, AI obrada, 30-s Garmin rok pri opterećenju, kvote pri velikom saobraćaju.
- Cloudflare Free resursi se ograničavaju prema planu; **ne prelaziti na Paid**. Ako se traži kartica ili plaćena nadogradnja, prekini i pošalji screenshot.

## Lokalno testiranje bez Cloudflare-a

```powershell
node --test .\test_worker.mjs
```

## Rollback

Render ostaje netaknut. Ako želiš da obrišeš samo sintetički Worker, možeš to uraditi u Cloudflare dashboardu; D1 bazu razmotriti zasebno. Ne menjati postojeći Neon SQL, ne revokovati Garmin OAuth i ne uključivati Garmin Endpoint Configuration.

## Zvanična dokumentacija

- https://developers.cloudflare.com/workers/wrangler/commands/workers/
- https://developers.cloudflare.com/workers/wrangler/commands/d1/
- https://developers.cloudflare.com/workers/configuration/secrets/
- https://developers.cloudflare.com/workers/platform/limits/
- https://developers.cloudflare.com/d1/platform/limits/
