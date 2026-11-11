# GarminAI Public v0.3 — bezbednosne granice

## Šta postoji
- `/mcp` zahteva razvojni statički Bearer token; čuva se samo SHA-256 otisak u Render okruženju.
- Bez konfiguracije server vraća 503 (fail closed). Neautorizovanim zahtevima vraća 401.
- Nema stvarnih Garmin naloga, tokena, baza, GDPR produkcionog režima ili uvida u korisničke podatke.
- `tenant_store.py` je ISKLJUČIVO primer izolacije, bez integracije sa MCP alatkama i bez trajne baze.
- Testovi potvrđuju da simulirani korisnik A ne čita podatke korisnika B u tom primeru.

## Šta NE postoji
- Prijava korisnika, token issuance, OAuth discovery, refresh, revoke, realna autorizacija na nivou korisnika.
- Garmin Business OAuth i Garmin Activity API integracija.
- Trajna baza, DB-level RLS, audit, rate limit, zaštita od zloupotrebe.
- Garancija da je servis spreman za stvarne podatke.

## Sledeća faza
Korisnik se prijavljuje putem odgovarajućeg identity providera; MCP servis kao resource server validira access token (issuer, audience, expires, scope), i iz verifikovanog subject-a izvodi tenant u svim upitima. Garmin OAuth je ODVOJEN tok kojim korisnik odobrava preuzimanje aktivnosti. Čuvati tokene šifrovano, primenjivati najmanje privilegije, revocation, delete, log redaction, testove cross-user pristupa i pristanak za AI obradu. Statistički i naučni sadržaj i dalje može biti javan, ali trening podaci zahtevaju izolaciju.

Demo Bearer token NIKADA ne koristiti kao individualnu prijavu korisnika.
