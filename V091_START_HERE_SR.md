# GarminAI Public v0.9.1 — ChatGPT CIMD / OAuth staging kompatibilnost

## Potvrđeni uzrok
ChatGPT šalje `client_id=https://chatgpt.com/oauth/client.json`, `redirect_uri=https://chatgpt.com/connector_platform_oauth_redirect`, `scope=openid email offline_access` i `resource=https://garminai-public-demo.onrender.com/mcp-oauth-staging`.

v0.9.0 je odbijao URL Client ID (`UNEXPECTED_CLIENT`), a zatim bi odbio `offline_access` (`UNSUPPORTED_SCOPE`). Ovo je ispravljeno **samo** za tačan ChatGPT CIMD URL i registrovani stabilni callback, bez dopuštanja proizvoljnih URL-ova ili scope-ova. Ostatak OAuth i MCP zaštita ostaje aktivan. Neon radi stvarnu CIMD validaciju, potpisivanje i verifikaciju OAuth zahteva, grant i proveru callback-a. Aplikacija samo dozvoljava tačan identitet i obavlja pre-validaciju.

Neon Managed Better Auth (2026-11-02): CIMD je podrazumevano uključen kad je podesen MCP resurs. **Nije potrebna ručna registracija klijenta u Neon Console** ako taj managed provider radi kako je dokumentovano. Ako live instanca odbije CIMD, proveriti Neon OAuth provider i `client_id_metadata_document_supported`; ne zaobilaziti provider proveru.

Dokument ChatGPT klijenta: https://chatgpt.com/oauth/client.json.

## GitHub / Render instalacija (0 € politika)
1. Raspakuj ZIP. Kopiraj **sadržaj foldera `public/`** u isti folder `public/` GitHub repozitorijuma `zbedic-tron/garminai`, zameni prethodne datoteke, uradi Commit i sačekaj Render Free deploy.
2. Potvrdi `/healthz` `version=0.9.1`; ponovi postojeći `/auth/oauth-test` E2E i očekuj prethodni PASS.
3. Na Render > Environment ostavi sva prethodna podešavanja, a dodaj tri vrednosti:

```
GARMINAI_CHATGPT_OAUTH_CLIENT_ID=https://chatgpt.com/oauth/client.json
GARMINAI_CHATGPT_OAUTH_CALLBACK=https://chatgpt.com/connector_platform_oauth_redirect
GARMINAI_CHATGPT_MCP_STAGING_ENABLED=1
```

4. Nakon primene promenljivih proveri `https://garminai-public-demo.onrender.com/auth/chatgpt/status`: `chatgpt_connector_enabled=true`, `chatgpt_config_issues=[]`, `expected_neon_registration=CIMD_DISCOVERY_NO_MANUAL_CLIENT`.
5. U već napravljenom privatnom ChatGPT pluginu `GarminAI MCP` klikni **Connect**. Očekivani tok: Neon Google sign-in → Consent → Approve → ChatGPT. Ovlašćenje je samo za izmišljene, read-only demo MCP alate. Ne objavljuj plugin javno.
6. Ako dobiješ grešku, zabeleži samo status/error code, bez query-stringa, koda, state, potpisa, verifiera, tokena, cookie-ja ili tajni.

Neon klijent `GarminAI OAuth E2E Test`, stari `/mcp` i izolacija korisnika ostaju neizmenjeni. Scope `offline_access` znači mogućnost osvežavanja tokena, ne pristup Garmin podacima. Neon mora da podrži `offline_access` i `refresh_token`; ako nije oglašeno ili se ne izdaje, treba proveriti Neon OAuth provider, ne nasilno preskočiti taj korak. Ako je `tools/list` dostupan, proveriti `get_sync_status` i `get_activities` i samo DEMO_ONLY podatke.

## Rollback
Postavi `GARMINAI_CHATGPT_MCP_STAGING_ENABLED=0` u Render > Environment i primeni konfiguraciju. Postojeći testni OAuth i demo endpoint se ne menjaju. Ne uključivati billing (GitHub, Render Free, Neon Free), ne koristiti OpenAI API ključ. Ne izlagati Garmin Connect naloge.

## Ograničenja
Lokalni unit/browser testovi ne dokazuju stvarni Neon CIMD discovery niti ChatGPT autorizaciju; prvi realni ChatGPT test tek sledi. Provider može odbiti scope, client registration ili token_endpoint_auth_method — tada stajemo i dijagnostikujemo bez popuštanja zaštite.

Izvori: https://neon.com/blog/managed-better-auth-oauth-provider-mcp ; https://developers.openai.com/plugins/build/auth ; https://better-auth.com/docs/plugins/oauth-provider/tokens
