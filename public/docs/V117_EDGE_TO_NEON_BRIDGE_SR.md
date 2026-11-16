# GarminAI Public 1.1.7 — Synthetic D1 → Neon bridge, bez produkcionog push-a

## Cilj

Odvojeni Cloudflare Worker (postojeća `edge_lab_v116` instanca) već je korisnički potvrdio sintetičke D1 upise u v1.1.6.4 (`200/200/409`). v1.1.7 omogućava *opcionu* proveru da Render može kroz **autentifikovani ChatGPT MCP** preuzeti jedan D1 sintetički receipt, upisati pripadajući fiktivni sažetak u **postojeći Neon RLS inbox** i tek potom obeležiti D1 događaj kao isporučen.

## Komponente

- `edge_lab_v116/bridge_v117.mjs`: tri strogo autentifikovane POST akcije `/_lab/bridge/seed`, `/claim`, `/ack`; GET `/_lab/bridge/status` bez identifikatora i tajni. U Worker-u nema poziva ka Renderu ili Neonu.
- `edge_lab_v116/schema_bridge_v117.sql`: zasebna D1 tabela `lab_bridge_v117`; jedinstveni `(recipient_key,event_id)`, `acked_at`; **ne izvršavati u Neon**. Ne dira staru `lab_events_v116` tabelu.
- `garminai_public/garmin_edge_to_neon_v117.py`: operator opt-in + potvrda + verifikovani Neon subject. Pseudonim za primaoca generiše HMAC sa zasebnom tajnom. Posle D1 potvrde, samo konstantni sintetički Garmin-like model u `OfflinePostgresPushInbox` (RLS/least privilege), pa D1 ACK.
- `mcp_oauth_demo.py`: novi privatni alat `run_synthetic_edge_to_neon_rehearsal`. Ranijih sedam alata nepromenjeno.
- `garmin_edge_to_neon_status_v117.py`: samo READ ONLY status, ne proverava uživo D1 ili Neon; nikad ne prijavljuje produkcionu spremnost.
- `edge_lab_v116/Install-Bridge-V117.ps1`: samo postojeći Cloudflare Workers Free + D1; ne pravi bazu; **ne pokreće se automatski na Renderu**; odvojena nasumična tajna dostupna kroz clipboard za Render UI, bez logovanja ili zapisivanja u repo.

## Bezbednosna sekvenca

1. MCP potvrda `RUN_SYNTHETIC_EDGE_TO_NEON` + `GARMINAI_EDGE_BRIDGE_STAGING_ENABLED=1` + tačno podešen URL i tajna.
2. `VerifiedPrincipal`, proverena Neon/garmin OAuth veza *na Render serveru*; na Cloudflare ide samo HMAC pseudonim. Ne ide Garmin ID.
3. D1: `seed` zapis ili postojeći identičan, `claim` i provera digest-a. D1 nema slobodan pristup ni Garmin poljima ni stvarnim podacima.
4. Neon: već postojeći `garminai.garmin_push_inbox`, RLS + FORCE RLS, `garminai_app` samo SELECT/INSERT; dva upisa uz jedinstveni ključ potvrđuju idempotentnost. Komit Neon transakcije prethodi D1 ACK-u.
5. D1 ACK potvrđuje `acked_at`. Ako se ACK izgubi, vraća se `NEON_COMMITTED_EDGE_ACK_PENDING`, sledeći poziv može sigurno ponoviti.

Zadržava **jedan fiktivni bridge zapis po korisniku** u D1 i isto toliko u Neonu. Zavisno od ranijeg v1.1.2 fixture-a Neon može imati i drugi, zaseban fiktivni red. Test ne dokazuje da su stvarni Garmin push događaji bezbedni ili dozvoljeni u ovoj arhitekturi.

## Preostale prepreke

Garmin verifikacija pošiljaoca, pravni/ugovorni pregled Cloudflare i AI, cold start/push SLA i obavezne kontrole brisanja, opoziva, troškova i podataka. Produkciona spremnost ostaje `BLOCKED`. **Ništa iz Garmin Developer Endpoint Configuration ne uključivati**.
