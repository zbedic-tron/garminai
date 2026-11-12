# v0.8 MCP identity verifier — bez produkcione aktivacije

Implementacija: `garminai_public/mcp_identity.py`.

Koristi samo **server-side proverene asimetrično potpisane OAuth access JWT tokene** iz unapred poznatog OIDC/OAuth izdavaoca. Publikovani JWKS treba preuzimati isključivo sa dokumentovanog HTTPS endpointa verifikovanog izdavaoca, uz rotaciju i adekvatno ograničenje keša. Provera iz ovog paketa prima JWKS u konstruktoru da bi testovi bili offline. U produkciji je neophodno proveriti i opoziv/sesijski životni ciklus u skladu sa izabranim provajderom.

Stabilni interni identitet `usr_` formira se isključivo od verifikovanog para `(issuer, sub)`. Ne sme se prihvatati od korisnika kao header, URL parametar ili MCP argument. Za Neon RLS `garminai.subject` mora se postaviti unutar transakcije iz tog identiteta, a ne iz slobodnog teksta.

**Status:** demo `/mcp` i dalje zaštićen zajedničkim developer tokenom; nijedna realna autentifikacija nije aktivirana. Nemoj unositi ili testirati stvarne Garmin korisnike.

Protokol: https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization
OpenAI Plugins auth: https://developers.openai.com/plugins/build/auth
