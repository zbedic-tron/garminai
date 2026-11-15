# GarminAI Public v0.8.8 — Neon OAuth + MCP demo (STAGING ONLY)

**Ovo je nastavak prethodnog uspešnog v0.8.7.4 PKCE/S256 testa.**
Neon iz prethodnog testa je jedini autoritet za OAuth tok. Ni jedan stvarni
Garmin nalog, privatna aktivnost, korisnička baza ili produkcioni MCP nije
povezan ovim paketom.

## Šta je novo

- Novi zaseban endpoint `https://garminai-public-demo.onrender.com/mcp-oauth-staging`.
- Prihvata isključivo **Neon OAuth access JWT** vezan za već podešeni staging
  resurs, prijavljenog klijenta i scope `openid`. Kriptografski proverava `iss`,
  `aud`, `exp`, `iat`, `azp`, tip `at+jwt`, potpis i `sub` pomoću javnog Neon JWKS.
- Opciono dostupna **dva read-only MCP alata**: `get_sync_status` i
  `get_activities`, koriste isključivo izmišljene demo aktivnosti.
- Nema OAuth tokena u browseru, logovima, bazi ili odgovoru korisniku. U
  postojećem PKCE testu token je samo kratkotrajno prosleđen kroz interno
  ASGI testiranje MCP transporta i odmah odbačen.
- Ne menja se postojeći `/mcp` sa posebnim, statičkim demo bearer ključem.
- Isključeno dok operator eksplicitno ne uključi **novu** Render promenljivu.

## Instalacija — bez ručnog uređivanja koda

1. Raspakuj ZIP.
2. U repozitorijum `zbedic-tron/garminai` prenesi sadržaj `public/` u postojeći
   direktorijum `public/` i `render.yaml` ako je potreban, pa Commit changes.
3. Sačekaj uspešan Render Deploy. Prvo proveri `/healthz` — verzija `0.8.8`.
4. Bez promene environment vrednosti, proveri `/auth/mcp-oauth/status`.
   `mcp_demo_oauth_tools_enabled` mora biti `false`.
5. U Render Dashboard > `garminai-public-demo` > Environment **dodaj**:

       GARMINAI_MCP_AUTH_TOOLS_STAGING_ENABLED = 1

   Sačuvaj promenu i izvrši novi deploy/restart ako Render to ne pokrene sam.
   Nemoj menjati postojeće Neon URL-ove, client ID, `GARMINAI_DEMO_TOKEN_SHA256`,
   niti uključivati Neon `Skip consent`.
6. Proveri `/auth/mcp-oauth/status`: `mcp_demo_oauth_tools_enabled: true`,
   `mcp_demo_oauth_config_issues: []`.
7. U **istoj kartici** otvori `/auth/oauth-test` i pokreni svežu autorizaciju:
   Google → Neon Consent → Approve → callback.
8. Očekivana završna poruka kada je i stvarni interni MCP JSON-RPC poziv prošao:

       PASS: Neon OAuth + PKCE + verified JWT + authenticated MCP demo tools/list.

   Aplikacija će pokušati i `get_sync_status` i prihvatiti proveru samo ako odgovor
   sadrži `DEMO_ONLY` oznaku. Ako se pojavi `PARTIAL PASS`, OAuth radi, ali
   MCP deo **nije potvrđen**. Sačuvaj screenshot poruke i statusa bez tokena.

## Vrednosti koje treba da ostanu kako jesu

- `GARMINAI_OAUTH_UI_STAGING_ENABLED=1`
- `GARMINAI_MCP_OAUTH_STAGING_ENABLED=1`
- `GARMINAI_OAUTH_E2E_STAGING_ENABLED=1`
- `GARMINAI_OAUTH_TEST_CLIENT_ID` — postojeći javni staging Client ID
- `NEON_AUTH_STAGING_URL` / `GARMINAI_MCP_OAUTH_STAGING_ISSUER` — isti issuer
- `RENDER_EXTERNAL_HOSTNAME` — Render host za demonstraciju
- Neon OAuth client redirect:
  `https://garminai-public-demo.onrender.com/auth/oauth-test/callback`
- Neon client resource:
  `https://garminai-public-demo.onrender.com/mcp-oauth-staging`

## Zaustavljanje staging testa

U Renderu postavi `GARMINAI_MCP_AUTH_TOOLS_STAGING_ENABLED=0` i sačuvaj.
Tada novi endpoint samo vraća OAuth 401 challenge bez MCP alata, a prethodni
OAuth E2E test nastavlja normalno da radi. Nakon završetka razvojne faze,
isključi i ostale staging prekidače prema prethodnim uputstvima.

## Bezbednosna ograničenja i testiranje

- Ne povezuje se ChatGPT kao dinamički registrirani OAuth klijent; koristi se
  samo jedan unapred registrovani Neon staging klijent.
- Scope `openid` ograničen je isključivo na izmišljene testne alate. Za
  produkcioni pristup privatnim aktivnostima potrebni su posebni resource
  scope-ovi, pregled dozvola, vezivanje identiteta i validacija privatnosti.
- JWT se proverava lokalno uz javni JWKS iz fiksnog Neon issuer-a. To ne znači
  trenutačno opozivanje tokena; token se može prihvatati do isteka vremena.
- Testovi su lokalni i koriste lažne ključeve i simulirane zahteve. U ovoj
  radnoj okolini nije dostupan Python MCP paket, pa kompletan MCP transport
  nije verifikovan na pravom Render servisu. Kao rezultat toga deploy + E2E
  browser proba su **obavezni** pre nego što proglasimo MCP integraciju uspešnom.
- Podrazumevani režim ostaje bez pristupa stvarnim podacima.

Relevantna uputstva: `public/docs/V088_NEON_MCP_AUTH_STAGING_SR.md`.
