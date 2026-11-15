# GarminAI Public v1.0.1 — počni ovde

**Diferencijalni ZIP**: samo nove/izmenjene datoteke od v1.0.0. Ne treba ponovo uploadovati ceo projekat.

1. Raspakuj ZIP; kopiraj njegov `public/` preko postojećeg `public/` u GitHub-u. `render.yaml` je u korenu repozitorijuma — zameni ga odvojeno ako koristiš Blueprint. Ne briši nijedan drugi fajl.
2. Uradi Commit → Render deploy → proveri `/healthz` (`1.0.1`).
3. Proveri `/garmin/integration/status`: `oauth_connect_enabled=false`, `push_ingestion_enabled=false` dok sve ne pripremimo.
4. Ne unositi stvarne Garmin Client Secret/ID u GitHub niti u ChatGPT.
5. **NE uključuj** `GARMINAI_GARMIN_LINK_STAGING_ENABLED=1` pre Neon SQL migracije, provere neprivilegovanog DB runtime naloga i `--no-access-log` podešavanja.
6. Nastavi sa detaljnim uputstvom `public/docs/V101_GARMIN_OAUTH_LINK_SR.md`. Sledeći korak radimo kroz Neon i Render UI, bez preskakanja.

Novine: izolovano Garmin OAuth2 PKCE povezivanje naloga uz proveren Neon identitet, korisnički consent, jednokratni browser-bound state, AES-GCM token storage i RLS; nova tri MCP alata za link/status/revokaciju. **Pravi Garmin trening podaci i Garmin push ostaju ISKLJUČENI**. Testovi su offline simulacije, a ne živa Garmin autorizacija. Politika: 0 € dodatnih troškova, bez javnog plugin objavljivanja.
