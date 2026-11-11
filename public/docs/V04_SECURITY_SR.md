# GarminAI Public v0.4 — bezbednosna granica

## Šta je implementirano
- Postojeći `/mcp` ostaje zaključan jednim operatorskim demo tokenom (`GARMINAI_DEMO_TOKEN_SHA256`).
- `DemoIdentityVerifier`: **isključivo lokalna testna simulacija** potpisanog identiteta sa izdavaocem, publikom i rokom važenja. Nije OAuth, nije javno dostupan i nije vezan za MCP.
- `TenantActivityDB`: izdvojeni SQLite testni sloj. Svaka INSERT/SELECT/UPDATE/DELETE operacija zahteva verifikovan identitet i koristi `owner_subject` u SQL uslovu.
- Testovi proveravaju da dva korisnika mogu imati isti ID aktivnosti bez međusobnog uvida i da brisanje jedne osobe ne dotiče drugu.
- Sve javne MCP alatke i dalje vraćaju isključivo izmišljene demonstracione podatke.

## Šta nije implementirano
- Nema korisničkog prijavljivanja, produkcionog identiteta, Garmin OAuth, ChatGPT OAuth, Garmin sinhronizacije ni čuvanja stvarnih aktivnosti.
- Nema produkcione baze, per-user kontrole pristupa u MCP alatkama ni token refresh-a.
- Demo HMAC testni identitet ne sme postati sredstvo prijavljivanja stvarnih korisnika.
- Bearer token iz v0.3 nije korisnički token: svi sa njim imaju isti pristup demo sadržaju.

## Redosled pre stvarnih korisnika
1. Odabrati provajdera identiteta koji podržava OAuth 2.1 / OIDC; implementirati verifikaciju `issuer`, `audience`, potpis/ključevi, rok, scope i opoziv prema dokumentovanom toku.
2. Implementirati OAuth Protected Resource Metadata za MCP, zahtevati važeće korisničke tokene pri svakom pristupu; Garmin OAuth kao **posebna autorizacija** za preuzimanje aktivnosti.
3. Produkciona baza i `owner_subject` iz verifikovanog tokena (nikada iz MCP parametra ili HTTP `X-User-ID` zaglavlja); dodatno koristiti RLS i testove za horizontalni pristup.
4. Enkriptovati Garmin tokene uz odvojeno upravljanje ključevima; logovi bez tajni i zdravstvenih podataka, odvojeni backup i brisanje na zahtev.
5. Pravna i bezbednosna provera Garmina, ChatGPT integracije, saglasnosti za AI procesiranje.

## Render Free
Ne čuvati stvarne naloge ili SQLite fajl na Render Free. Lokalni fajlovi nestaju posle sleep/redeploy; besplatna Postgres instanca ima ograničen vek. Testovi koriste SQLite `:memory:` isključivo lokalno.

## Token rotacija
Nakon ranijeg prikazivanja dela tokena u snimku, generisati potpuno novi demo token, postaviti novi SHA256 u Render Environment i zameniti `Authorization: Bearer ...` u Inspectoru. Nikad ne slati vrednost u chat/GitHub.
