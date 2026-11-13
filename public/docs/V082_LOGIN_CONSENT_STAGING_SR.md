# GarminAI Public v0.8.2 — Login i Consent, bezbedna staging verzija

## Šta zaista radi

Dve javne, HTTPS stranice su pripremljene na postojećem Render servisu:

- `/auth/login`
- `/auth/consent`

Stranice su jasno označene kao **staging**. Nijedna ne kreira sesiju, ne prijavljuje korisnika, ne dodeljuje OAuth dozvolu i ne prima Garmin tokene. Nema aktivnog dugmeta za odobrenje. Upiti iz URL-a se ne prikazuju u HTML-u ni logovima. Dodata su `no-store`, `no-referrer`, anti-frame i restriktivna CSP zaglavlja. MCP i dalje služi samo izmišljene podatke.

## Zašto još nije funkcionalan login

Neon Managed Better Auth OAuth Provider zahteva *funkcionalnu* korisničku sesiju i konzistentan potpisani `oauth_query`. Na consent stranici mora da se prikaže validiran klijent i traženi scope, a odobrenje se mora poslati zvaničnom Better Auth OAuth consent mehanizmu (sa aktivnom sesijom, server-side validacijom i zaštitom od CSRF). Puko prosleđivanje URL parametara ili automatski `accept:true` nije bezbedno. Zato ova verzija **nije spremna za uključivanje Neon OAuth providera**.

## Postavljanje

1. Kopiraj sadržaj ZIP-ovog `public/` u postojeći `public/` na GitHub-u; `render.yaml` ostaje u korenu.
2. Sačekaj Render automatski deploy, proveri `/healthz` => `0.8.2` i Render Logs `GARMINAI_DB_CHECK: PASS (OK)`.
3. Poseti `/auth/login` i `/auth/consent`; obe stranice prikazuju eksplicitno upozorenje o staging režimu.
4. `/auth/development-status` prikazuje `mcp_oauth_enabled:false`, `consent_submission_enabled:false`.
5. **U Neon Console ne klikći `Enable` za OAuth Provider**; ako je modal već otvoren, izaberi Cancel. Ne unosi credentials, ne dodaj environment secrets.

## Potrebno za sledeći korak (v0.8.3)

- Implementirati login i session kroz podržani Neon Auth klijent (prema aktuelnoj verziji SDK-a).
- Na consent prikazati samo validirane, potpisane OAuth podatke (identitet klijenta, redirect host, scopes), uz `Accept` i `Deny`.
- Pozvati službeni `oauth2.consent` endpoint sa sesijom i originalnim potpisanim `oauth_query`; testirati izmene parametara i istek.
- U MCP implementirati zaštićeni resurs metadata, proveru JWT potpisa i `aud`, `iss`, `exp`, `scope` za SVAKI zahtev, a OAuth 401 izazov; tek onda ukloniti DEMO_BEARER_GATE za stvarne korisnike.
- Posebna Garmin OAuth saglasnost, pažljiva kontrola AI obrade i ograničenje prema pravilima Garmin Activity API-ja.

## Reference

- Neon Managed Better Auth OAuth Provider: https://neon.com/blog/managed-better-auth-oauth-provider-mcp
- Better Auth sign-in / consent: https://better-auth.com/docs/plugins/oauth-provider/sign-in-flow
- Better Auth OAuth Provider: https://better-auth.com/docs/plugins/oauth-provider

Privatna Windows GarminAI aplikacija nije deo ovog paketa.
