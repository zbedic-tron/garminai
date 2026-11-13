# GarminAI v0.8.5 — staging-only OAuth resource discovery

Implementacija: `garminai_public/oauth_resource_staging.py`, proširenje `mcp_identity.py`.

### Razdvojene granice poverenja

- `GET /auth/mcp-oauth/status` prikazuje samo javne indikatore spremnosti.
- `GET /.well-known/oauth-protected-resource/mcp-oauth-staging` vraća metapodatke **samo** kada su oba izričita operaterska podešavanja prisutna, a izdavalac identičan konfigurisanom URL-u Neon `auth-staging` grane.
- `GET|POST /mcp-oauth-staging` vraća **401** i RFC-style `WWW-Authenticate` challenge u testnom režimu. **Ne pokreće MCP.** Dok je režim isključen, ove dve putanje vraćaju 404.
- Postojeći `/mcp` **nije izmenjen**: iza demo bearer zaštite vraća samo fikcionalne podatke.
- `MCPAccessTokenVerifier.verify(..., required_scopes=...)` nakon kriptografske validacije proverava i dozvole iz potpisanog tokena, ali je još offline/nezakačen na mrežni servis.

### Fail-closed konfiguracija

Podrazumevano je `GARMINAI_MCP_OAUTH_STAGING_ENABLED` odsutan ili `0`, tako da testni endpoint nije aktivan.

*Buduće*, tek nakon proverene Neon OAuth Provider konfiguracije:

- `GARMINAI_MCP_OAUTH_STAGING_ENABLED=1`
- `GARMINAI_MCP_OAUTH_STAGING_ISSUER=<tačan issuer iz official discovery dokumenta>`
- `NEON_AUTH_STAGING_URL=<već konfigurisan URL staging grane>`

Namerno odbijamo očekivani izdavalac koji ne odgovara operaterski navedenom staging Auth URL-u. Ako Neon u svom discovery dokumentu koristi drugačiji legitimni kanonski issuer, treba prilagoditi validaciju tek nakon poređenja i stručne revizije; ne zaobilaziti pravila.

### Ostalo za produkciju

- Test sa stvarnim Neon izdavaocem i issuer identification / PKCE.
- JWKS osvežavanje, rotacija, provera tokena pri svakom MCP pozivu, scope i `aud` enforcement.
- Sigurna consent stranica, očuvanje `oauth_query` i verificirana sesija, bez lažnih potvrda pristanka.
- Per-tool MCP `securitySchemes`, ChatGPT linking test i per-user RLS.

**Nema obrade stvarnih Garmin podataka.**
