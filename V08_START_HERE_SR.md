# GarminAI Public v0.8.0 — MCP Identity Verification (STAGING)

## Šta je zaista urađeno

- Osnova je v0.7.1. Svih 6 MCP alatki, literatura, Garmin OAuth staging i Neon provere su očuvani.
- Novi `public/garminai_public/mcp_identity.py` radi **offline proveru potpisanih RS256 OAuth pristupnih tokena**: jedinstveni `kid`, potpis prema poznatom JWKS-u, tačan HTTPS `iss`, tačan `aud` za MCP resurs, `exp`, `iat`, ne-prazan `sub`.
- Iz proverene kombinacije izdavalac+identifikator izračunava se stabilni interni `usr_...` identitet za kasniji PostgreSQL kontekst; ne veruje se proizvoljnom HTTP zaglavlju ili tool parametru.
- Dodat je `PyJWT[crypto]` i testovi protiv pogrešnog issuer/audience, lažnog potpisa, isteklih i nepotpisanih tokena.
- Lokalno: **69 testova prošlo** (ukupno, uključujući prethodne testove).

## Šta NIJE završeno

- Nijedan pravi korisnik nije autentifikovan. Nije izabran/konfigurisan stvarni OAuth/OIDC izdavalac, nema prijave, nema JWKS preuzimanja/rotacije ključeva, nema MCP autorizacionog discovery toka.
- `/mcp` ostaje sa postojećim DEMO Bearer tokenom i isključivo izmišljenim podacima.
- Garmin OAuth i realni Activity API ostaju isključeni. Modul za identitet NIJE povezan na javnu rutu.
- Za produkciju su potrebni validacioni testovi sa pravim autorizacionim serverom, provera scopes i tokovâ opoziva tokena, zaštita sesija, zajednički RLS identitet i korisnički pristanak.

## Kako postaviti na GitHub

1. Raspakuj ZIP.
2. **Sadržaj** `public/` prebaci u postojeći `public/` folder na GitHub-u; ne pravi `public/public/`.
3. Ako se `render.yaml` razlikuje, postavi ga samo u koren repozitorijuma.
4. `Commit changes`; Render treba automatski da se ažurira.
5. Proveri `/healthz` (`0.8.0`) i Render Logs `GARMINAI_DB_CHECK: PASS (OK)`.

**Ne menjaj** `DATABASE_URL`, demo token, Garmin ključeve, SQL šemu, Windows GarminAI. Ova nadogradnja ne zahteva nove env promenljive.

## Sledeći arhitektonski korak

Odabrati stvarnog OAuth/OIDC izdavaoca sa besplatnim uslovima za pilot i proveriti dostupnost ChatGPT povezivanja. ChatGPT i Garmin izdaju **različite** tokene. MCP server nikada ne sme da prihvata Garmin token umesto svog pristupnog tokena. Zatim implementirati protected-resource metadata (RFC9728), issuer metadata, OAuth authorization code + PKCE, exact redirect_uri, audience/resource proveru, rotaciju ključeva i aplikaciono vezivanje identiteta.

Cilj 0 EUR ostaje **cilj**, ne bezuslovna garancija. Na Render Free moguća su uspavljivanja i prekidi.
