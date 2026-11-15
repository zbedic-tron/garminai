# GarminAI Public v0.8.7.2 — Neon signed-query ba_param parser fix

## Uzrok i ispravka

Neon na `/auth/login` šalje ponovljene `ba_param` vrednosti da navede koja polja ulaze u potpis, uključujući `ba_param=ba_param`. v0.8.7.1 je pogrešno primenjivao pravilo „tačno jedan parametar“ i na `ba_param`, što je rezultovalo `INVALID_SIGNED_REQUEST` čak i kada su `sig` i `ba_param` bili prisutni.

v0.8.7.2 dozvoljava ponavljanja **samo liste `ba_param`**, zadržava proveru jedinstvenosti njenih naziva i tačno po jednog primerka svakog drugog potpisanog parametra. Spisak potpisanih polja i `sig` se prosleđuju Neonu; GarminAI ne tvrdi da proverava kriptografski potpis u browseru. Neon ostaje odgovoran za proveru pri obradi `oauth_query`.

## Deployment

1. Raspakuj ZIP i prenesi **sadržaj `public/`** u postojeći `public/` repozitorijuma. GitHub commit, Render deploy.
2. **Nema SQL migracija i nema novih Render promenljivih.** Sačuvaj `GARMINAI_OAUTH_UI_STAGING_ENABLED=1`, `GARMINAI_OAUTH_E2E_STAGING_ENABLED=1`, `GARMINAI_MCP_OAUTH_STAGING_ENABLED=1` i postojeće Neon staging URL, issuer i testni Client ID.
3. Proveri `/healthz` (`version=0.8.7.2`) i `/auth/oauth-ui/status` (`oauth_ui_staging_enabled=true`, `oauth_ui_config_errors=[]`).
4. Otvori `https://garminai-public-demo.onrender.com/auth/oauth-test` i započni **novi** OAuth test. Ne koristi već podeljen ili istekao OAuth URL.
5. Javi samo sledeći status prikazan na ekranu (npr. Google login, consent ili dijagnostički kod), **bez slanja punih OAuth adresa, `sig`, `state`, `code`, tokena, kolačića ili session verifiera**.

## Bezbednost i ograničenja

- Ovo je lokalni parser fix; stvarni Neon end-to-end tok **nije potvrđen** dok se ne proveri nakon Render deploymenta.
- Nema izmena baze/RLS, `/mcp` demo gate-a, produkcionog auth-a ili Garmin podataka.
- OAuth UI je još javno dostupno testno okruženje. Nakon testiranja možeš isključiti staging prekidače.

Izvor: https://better-auth.com/docs/plugins/oauth-provider/sign-in-flow
