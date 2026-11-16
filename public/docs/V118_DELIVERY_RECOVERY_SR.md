# v1.1.8 — Sintetički D1→Neon oporavak

Ovaj dodatak je operator-controlled i namenjen samo fiktivnim događajima. Potvrđen je prethodni v1.1.7 E2E PASS; v1.1.8 je nova, **zasebna** fiksna simulacija po prijavljenom Neon subject-u. D1 pseudonim formira HMAC nad verifikovanim subject-om i postojećim Bridge secret-om; Garmin ID/subject, tokeni i stvarni treninzi se ne čuvaju u Cloudflare-u. D1 događaj koristi novi `SYNTHETIC_RECOVERY_V118_` prefiks.

`recovery_v118.mjs` prihvata samo `kind:SYNTHETIC_RECOVERY`, tačan oblik JSON-a i HMAC event binding. `seed` kreira ili proverava jedan red, `claim` povećava brojač pokušaja, `inspect` čita status, `ack` ostaje poseban poziv isključivo nakon Neon transakcije. Svaka remote mutacija zahteva `BRIDGE_TOKEN`; Worker nikad ne poziva Render ili Neon.

Render alat `run_synthetic_delivery_recovery` podržava četiri **izričito sintetička** scenarija. `SIMULATE_RENDER_DELAY` je namerno zaustavljanje posle D1 seed (nije stvarni cold-start), `SIMULATE_NEON_UNAVAILABLE` namerno preskače Neon, `SIMULATE_D1_ACK_UNAVAILABLE` potvrđuje Neon upis ali namerno preskače ACK, `RECOVER` ponavlja `INSERT ... ON CONFLICT` i vrši D1 ACK. Ako pravi Neon write ili D1 ACK ne uspe, rezultat nije PASS i stanje je bezbedno za ponavljanje. Identitet se proverava server-side; nije preuzet od Worker-a. Aktivnosti su fiksne konstante i ne mogu se zadati od strane MCP korisnika.

Novi MCP `get_synthetic_delivery_recovery_status` pročita D1 `inspect` samo za prijavljenog korisnika i vraća `PENDING_SYNTHETIC` ili `ACKED_SYNTHETIC` sa brojem claim pokušaja. Ne tvrdi da je nezavisno izvršena Neon revizija. Nova javna ruta `/garmin/ingress/delivery-recovery` **ne čita** D1 i ne otkriva pojedinačne rezultate; samo navodi booleans i `production_readiness:BLOCKED`.

D1 `schema_recovery_v118.sql` se izvodi samo preko Wrangler-a na **postojećoj** D1 bazi. Postojeći v1.1.6/1.1.7 događaji i LAB_TOKEN/BRIDGE_TOKEN ostaju nepromenjeni. Nema novog SQL-a za Neon, nema Garmin push ingest-a, nema background poller-a, nema plaćenih servisa.

Sigurnosna ograničenja: bez produkcione autentičnosti Garmin pošiljaoca, bez dokazane 30s pouzdanosti / Render Free cold-start-a, bez odobrenja trećih strana i AI obradu Garmin podataka. Ne stavljati Worker URL u Garmin Endpoint Configuration. Nove greške obrađuju se status kodovima bez server tajni ili mrežnih URL-ova.

Detaljan operator postupak: `V118_START_HERE_SR.md` u korenu ZIP-a i `public/docs/PROJECT_CONTINUITY_SR.md`.
