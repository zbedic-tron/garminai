# Edge lab v1.1.5 — samo sintetički podaci

OVAJ RADNIK NIJE INSTALIRAN, NIJE POVEZAN SA GARMINOM I NIJE PRODUKCIONI WEBHOOK.

- `worker.mjs`: opcioni Cloudflare Workers **sintetički-only** prototip. Podrazumevano vraća `LAB_DISABLED` (503).
- `schema.sql`: isključivo D1 laboratorijska tabela, ne pokretati u Neon-u.
- `test_worker.mjs`: lokalni Node 20+ testovi sa simuliranom D1 bazom, bez naloga, interneta ili novih servisa.
- Svi realni Garmin oblici poruka, uključujući `activities`, odbijaju se bez upisa.
- Za upis je potrebna operatorska tajna `LAB_TOKEN` od najmanje 32 nasumična karaktera i flag `LAB_SYNTHETIC_ONLY=1`; nijedna vrednost nije u ZIP-u.
- Po uspešnom D1 INSERT/SELECT vraća HTTP 200. Pri grešci baze vraća 503, a konflikt sa istim ID i drugim sadržajem 409.
- Pokazuje da odloženi Render ne mora usporavati potvrdu prijema: Worker se ne obraća Renderu. **Ne dokazuje stvarne rokove u Cloudflare-u**, dostupnost, ispravno odobrenje podataka, autentifikaciju Garmin pošiljaoca niti obradu/redrive.
- Ne koristi ni ne tvrdi verifikaciju `X-Forwarded-For`, `CF-Connecting-IP` ili drugih zaglavlja.
- Ne postavljati ovaj Worker na Cloudflare dok se posebno ne razmotri pravna/ugovorna dozvoljenost dodatnog provajdera, njegov Free plan, privatnost i bezbednost. Nije obavezan za instalaciju v1.1.5.
