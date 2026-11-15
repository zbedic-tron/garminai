# v0.9.2 — ChatGPT MCP stabilizacija (staging-only)

## Izvedene izmene

1. `oauth_e2e_staging._check_jwt`: nakon verifikacije potpisa + svih ranijih claim provera eksplicitno odbija `exp <= time.time()`; time se za access-token rok ne koristi 30 s JWT leeway. Bez čuvanja tokena, bez refresh toka na resource serveru.
2. `mcp_oauth_gateway.StagingOAuthGate`: `401` sada izričito dodaje `error="invalid_token"` uz postojeći `resource_metadata`; `503` ima `Retry-After: 5`. Za deklarisano telo preko 64 KiB vraća se `413` pre JWKS poziva, a neispravna deklaracija dužine daje `400`. Za bilo koji zahtev bez validnog JWT ostaje zatvoren pristup MCP alatima.
3. `mcp_oauth_demo`: opisna dokumentacija za ChatGPT nedvosmisleno označava sve alate kao demo/fikciju, bez menjanja naziva, potpisa, read-only ponašanja ili sadržaja.
4. `tests/test_mcp_stabilization_v092.py`: novi regresioni testovi za striktan istek, simulirani novi access token (isti `sub`), dva konkurentna subjekta i strane ID-jeve, neodobreni `azp` / `aud` / scope, nedostajući token, veliki deklarisani zahtev i izostanak JWKS.

## Nije implementirano namerno

- Nema Garmin Connect pristupa, live sportskih podataka, trajnog korisničkog skladišta ni javne distribucije plugina.
- Nema obrade `refresh_token` u aplikaciji: podaci o osvežavanju pripadaju OAuth klijentu/Neon authorization serveru. Samo novi, valjan access token može ponovo da prođe resource gate.
- Nema automatskog prespajanja naloga, ni lažne tvrdnje da je izveden test sa dva stvarna ChatGPT naloga.
- Preliminarna granica na `Content-Length` ne ograničava svako moguće chunked telo; konačna zaštita zavisi i od HTTP/MCP transporta i eventualnog reverse-proxy limita.

## Bezbednosni invariantni

- Dozvoljeni identitet klijenta tačno iz Render konfiguracije i ChatGPT CIMD URL-a, bez proizvoljnog otkrivanja URL-ova.
- Verifikuju se JWT `kid`, potpis, `typ`, `issuer`, `audience`, `azp`, `scope`, `iat`, `exp` i obavezni subject, na ključevima sa fiksnog Neon issuer-a.
- OAuth resource URL, callback allowlist, PKCE, Neon potpisani zahtevi i raniji consent mehanizam ostaju.
- Per-request identitet se prenosi isključivo kroz ASGI scope, ne kao korisnički unet `user_id` ili HTTP header; Authorization header se ne prosleđuje MCP alatima.
- Odgovori ne otkrivaju subject, bearer, refresh tokene, cookie ili potpisani OAuth query.
- GitHub/Render/Neon ostaju na Free planovima. **0 € novih troškova**.

## Test i produkcioni nivo dokaza

Pokrenuto u razvojnom okruženju: `PYTHONPATH=. python -m unittest discover -s tests -p 'test_*.py' -q`; browser simulacije iz `tests/js/` koriste izvorne JS konstante i Node. U trenutnom okruženju Python `mcp` paket nije dostupan, pa lokalno nije ponovljen pravi FastMCP transport. Live ChatGPT konekcija će tek nakon deploymenta potvrditi kompatibilnost.

Korisni standardi: [MCP Authorization 2026-07-28](https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/docs/specification/2026-07-28/basic/authorization/index.mdx), [Python SDK tool descriptions](https://github.com/modelcontextprotocol/python-sdk/blob/main/docs/servers/tools.md).
