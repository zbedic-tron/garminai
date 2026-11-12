# GarminAI Public v0.8.1 — Izbor OAuth pružaoca (staging)

## Šta je stvarno urađeno

- Uveden **offline** validator metapodataka potencijalnog OAuth pružaoca (issuer, HTTPS endpoints, authorization-code, PKCE S256, CIMD ili DCR).
- Dodat `/auth/development-status`, bez tajni i bez poziva prema pružaocu identiteta.
- Postojeći MCP `/mcp` i dalje štiti zajednički DEMO Bearer, služi samo izmišljenim aktivnostima.
- Nisu dodati realna prijava, auth code/token endpoint, provider JWKS fetch, autorizacija Garmin naloga ili obrada stvarnih aktivnosti.
- Testovi rade potpuno offline, bez korisničkih naloga.

## Zašto ne koristimo Garmin prijavu kao MCP OAuth?

Garmin authorization code služi za saglasnost nad Garmin treninzima. ChatGPT traži zasebnu OAuth autorizaciju MCP resource servera. Token za Garmin Activity API nije pristupni token za GarminAI MCP.

## Šta mora da podrži budući besplatni IdP?

1. OAuth authorization-code + S256 PKCE.
2. CIMD (poželjno) ili DCR za ChatGPT prijavu.
3. HTTPS discovery i konzistentan issuer; bez korisnički kontrolisanog URL-a.
4. Resource-bound token (`aud`/`resource`) i scopes; JWKS ili pouzdana introspekcija.
5. Pregled besplatnih limita i prava na obradu podataka, bez uslovljavanja plaćenim paketom.

**Važno:** PASS offline validatora samo kaže da metapodaci izgledaju kompatibilno. Ne dokazuje da se ChatGPT stvarno prijavljuje. Potrebna je end-to-end provera pre aktivacije.

## Sledeći korak

Izaberemo konkretnog besplatnog IdP-a, proverimo besplatni plan i testiramo MCP OAuth discovery / login / consent / revocation sa testnim identitetom. Tek tada uvodimo vezu subject → Garmin OAuth autorizacija; nikada ne skladištimo Garmin ključeve u ChatGPT-u.

## Izvori

- https://developers.openai.com/plugins/build/auth
- https://developers.openai.com/api/docs/guides/custom-mcp-server
- https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization
