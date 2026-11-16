# GarminAI Public v1.1.5 — sintetička Edge/D1 laboratorija (bez produkcionog prijema)

## Glavni zaključak

Na postojećem Render Free hostingu **ne možemo garantovati** odgovor unutar Garminovih 30 s (hladno buđenje traje približno minut). Ne smemo tretirati `X-Forwarded-For` kao dokaz identiteta Garmin pošiljaoca. Readiness je i dalje `BLOCKED`.

Za hipotetičku kasniju arhitekturu ispitujemo odvajanje prijema od Rendera:

`izvor -> edge webhook -> trajni red u D1 -> HTTP 200 -> naknadna potvrđena obrada u Render/Neon`

U **v1.1.5 to ne radi sa stvarnim Garmin podacima**, nema dostupnog Garmin ulaznog endpointa u Cloudflare-u niti automatskog prenosa u Neon. Prototip je samo `public/edge_lab_v115/worker.mjs`, koji prihvata striktno sintetičke oznake i čuva digest bez stvarnih aktivnosti ili korisničkih ID-eva.

### Šta laboratorija dokazuje / ne dokazuje

- Lokalna simulacija D1 pokazuje da je `200` moguć tek **posle potvrđenog upisa**, a pad baze daje `503`.
- Jedinstveni `event_id` štiti od duplikata; drugi sadržaj sa istim ID-em se odbija sa `409`.
- Nema poziva ka Renderu u putanji potvrde: simulirani Render cold start ne blokira **sintetički** odgovor.
- Stvarni vremenski rok, autentifikacija Garmin pošiljaoca, pouzdanost D1, kvote, ponovno slanje, revokacije, brisanje i troškovi nisu provereni u produkciji.
- `CF-Connecting-IP` se može tumačiti samo uz eksplicitno dokazanu Cloudflare edge/proxy trust granicu. Nema pretpostavke o autentifikaciji Garmin zahteva. Ne objavljivati partner CIDR opsege.
- Garmin ugovor obavezuje na posebnu proveru svakog novog provajdera i AI podataka. Cloudflare nije ovim odobren kao primalac stvarnih Garmin podataka.

### Kako testirati bez Cloudflare naloga

Iz `public/` foldera:

```bash
node --test edge_lab_v115/test_worker.mjs
python -m unittest discover -s tests -p 'test_*.py'
```

**Ne pokretati** `edge_lab_v115/schema.sql` u Neonu. Nema novih Neon migracija ni Render promenljivih. Ne uključivati Garmin Endpoint Configuration. Ako se kasnije razmotri Cloudflare Workers Free/D1, potrebno je proveriti limit potrošnje, ugovorne dozvole i bezbednosni model **pre** otvaranja bilo kakvog webhooka.

### Javni status nakon Render deploymenta

- `/healthz` → `1.1.5`
- `/garmin/ingress/readiness` → `readiness: BLOCKED`, `live_garmin_push_enabled: false`
- `/garmin/ingress/edge-lab` → `mode: OFFLINE_SYNTHETIC_EDGE_LAB`, `edge_worker_deployed_by_garminai: false`
- `/garmin/integration/status` → `push_ingestion_enabled: false` i `mcp_real_garmin_data_enabled: false`
- `/garmin/push/activities` → `503`; ostatak Garmin push ruta takođe blokiran.

### Izvori za proveru uslova (javni)

- Render Free: https://render.com/docs/free
- Cloudflare Workers free limits: https://developers.cloudflare.com/workers/platform/pricing/
- Cloudflare D1 limits: https://developers.cloudflare.com/d1/platform/limits/
- Cloudflare original client IP headers: https://developers.cloudflare.com/fundamentals/reference/http-headers/
- Garmin partner PDF dokumentacija: poverljiva, nije deo javnog GitHub repozitorijuma.

### Rollback

Vrati samo v1.1.4 kod; baza i postojeća autentifikacija ostaju nepromenjene.

### Rezultati testova pri izdavanju

`python -m pytest -q`: **228 passed i 104 subtests passed**. Četiri JS browser skripte: **63 simulacije**, novi Node Worker: **11 testova**. Potpuni ASGI/MCP startup nije lokalno izvršen zbog nedostajućeg `mcp` paketa u radnom okruženju; Render deployment treba zasebno potvrditi.
