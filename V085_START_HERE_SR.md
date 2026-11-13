# GarminAI Public v0.8.5 — OAuth Resource Staging

## Šta smo uradili

**Samo razvojna / testna nadogradnja.** Pripremili smo standardni ugovor za otkrivanje MCP OAuth resursa (RFC 9728 / `WWW-Authenticate`) i dodatne testove provere potpisanog pristupnog tokena: potpis RSA, `iss`, `aud`, `exp`, `iat` i dozvole (`scope`). Ovo je priprema za **Neon Managed Better Auth kao OAuth provajder**.

**Ništa još nije otvoreno za stvarne korisnike:** postojeći `/mcp` ostaje iza starog **demo** tokena i vraća samo **izmišljene aktivnosti**. Ne menjamo Garmin credentials, Neon's `production` ili `auth-staging` konfiguraciju, niti Windows GarminAI. Ne pokrećemo dodatni servis i ne menjamo PostgreSQL šemu.

## Korak 1 — ažuriraj GitHub

1. Raspakuj ZIP na računar.
2. U `https://github.com/zbedic-tron/garminai` prenesi **sadržaj `public/` iz ZIP-a u postojeći `public/`**; nemoj praviti `public/public/`.
3. Datoteka `render.yaml` ide u koren, kao i ranije. Nije neophodno menjati je ako je ista.
4. Potvrdi **Commit changes**.
5. Na Renderu sačekaj završetak deploymenta, zatim otvori `https://garminai-public-demo.onrender.com/healthz`.

Očekivano: `"version":"0.8.5"`, `"mode":"DEMO_ONLY"`.

## Korak 2 — proveri status, bez uključivanja OAuth-a

Otvori:

`https://garminai-public-demo.onrender.com/auth/mcp-oauth/status`

Očekivano:

- `"version":"0.8.5"`
- `"mode":"STAGING_ONLY"`
- `"mcp_oauth_staging_enabled":false`
- `"mcp_authenticated_tools_enabled":false`
- `"garmin_live_data_enabled":false`

Provera `GARMINAI_DB_CHECK: PASS (OK)` i dalje treba da stoji u Render Logs.

**Ne dodaj sada `GARMINAI_MCP_OAUTH_STAGING_ENABLED` niti `GARMINAI_MCP_OAUTH_STAGING_ISSUER`.** Ti prekidači služe za sledeći, kontrolisani test kada završimo Neon login + consent i kada iz njihovog javnog discovery dokumenta proverimo tačan `issuer`. Ne nagađati issuer.

## Šta je pripremljeno, ali namerno isključeno

- `GET /.well-known/oauth-protected-resource/mcp-oauth-staging` — izdaje OAuth protected resource metapodatke **samo** kada je testni režim eksplicitno omogućen sa provereno identičnim `issuer`-om.
- `/mcp-oauth-staging` — testni `401 WWW-Authenticate` izazov. **Nije pravi MCP endpoint, ne obrađuje alate i nikada ne daje korisničke podatke.**
- `MCPAccessTokenVerifier` — kriptografske provere pripremljene i lokalno testirane sa izmišljenim JWT tokenima. **Još nije povezan sa mrežnim JWKS-om i javnim MCP saobraćajem.**

## Šta je sledeće (v0.8.6)

1. Testirati Neon OAuth Provider sa zasebnim `auth-staging` identitetima i stvarnim potpisanim `oauth_query` parametrom.
2. Implementirati stranicu za prikaz i **prihvatanje/odbijanje** MCP saglasnosti isključivo pomoću zvaničnog Neon/Better Auth protokola; nikad prihvatati klijentov samoprijavljeni identitet.
3. Potvrditi tačan `issuer`, JWKS, audience/resource i scope u stvarno izdatom pristupnom tokenu.
4. Tek zatim povezati autentifikaciju sa MCP alatkama, proveravati token **za svaki zahtev** i izolovati dva testna korisnika.
5. Prave Garmin aktivnosti tek kada Garminovi uslovi, zasebna AI saglasnost, korisnička prava i sigurnost prođu pregled.

## Bezbednost i troškovi

- **Ne šalji** ChatGPT-u Client Secret, DB URL, Google session cookie, Neon verifikator ili access token.
- Ne treba nijedna nova Environment promenljiva za ovaj deployment.
- Cilj ostaje 0 € obaveznih mesečnih troškova na postojećim besplatnim planovima, uz njihove limite.

Izvori:
- https://developers.openai.com/plugins/build/auth
- https://neon.com/blog/managed-better-auth-oauth-provider-mcp
- https://better-auth.com/docs/plugins/oauth-provider/sign-in-flow
