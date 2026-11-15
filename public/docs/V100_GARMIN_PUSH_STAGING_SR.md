# GarminAI Public v1.0.0 — tehničke granice Activity API staginga

**Ovo nije produkcioni Garmin webhook i ne treba ga registrovati u Garmin API Tools.**

Postojeće aplikacije: `/mcp` (nezavisan demo bearer gate), `/mcp-oauth-staging` (Neon JWT + ChatGPT CIMD), `/auth/oauth-test` (testni OAuth E2E) ostaju sa istim imenima i ponašanjem. Nema pristupa stvarnim Garmin podacima.

- `/garmin/integration/status` — samo statusi i spisak blokirajućih uslova. Bez poverljivih vrednosti.
- `/garmin/oauth/callback` — 503 dok povezivanje Garmin naloga nije bezbedno izvedeno.
- `/garmin/push/...` — 503 na svaki POST bez parsiranja/nastavka; svi URL-ovi su **rezervisani samo za budući kod**.
- `garmin_activity_staging.parse_activity_push` — lokalni strogi parser za reprezentativni `{"activities": [...]}` payload; ne prihvata druge tipove dok partner dokumentacija ne potvrdi šemu. Bez mreže, baze, zapisivanja, Garmin API poziva i tajnih ključeva.
- `prepare_for_owner` — simulira vezivanje isključivo za verifikovani interni `VerifiedPrincipal` i Garmin ID iz zasebne, pouzdane baze. Push telo nije dokaz porekla i ne može da izabere Neon's `sub`.

Bezbednosni checklist za nastavak implementacije:
1. Proveriti tačan zahtev Garminovog sender authentication protokola i njegovu dostupnost u Starter režimu. Ako se koristi nedokumentovani postupak, **ostati fail-closed**.
2. Povezivanje korisnika sa Garmin nalogom mora biti inicirano iz odgovarajuće autentifikovane sesije, sa revokacijom i izričitim pristankom; callback ne sme pouzdati identitetu iz query parametra.
3. Podatke i šifrovane tokene treba trajno čuvati u Neon-u sa atomarnom rotacijom refresh tokena, RLS izolacijom i pravilima brisanja.
4. Posebno pregledati dozvole za Garmin Activity Export, pravila čuvanja i prosleđivanja podataka trećim AI servisima. Ne prosleđivati stvarne podatke u ChatGPT bez ove provere i informisanog pristanka.
5. Testirati rate/burst limit, retry i idempotency pri ponovljenom slanju, kao i odbijanje svih nepoznatih korisnika pre bilo kakvog upisa.

Svi primeri u testovima su namerno **izmišljeni**, uključujući Garmin userId, summaryId, datume i udaljenosti. Ova verzija ne zahteva SQL migracije.
