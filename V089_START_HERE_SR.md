# GarminAI Public v0.8.9 — Neon OAuth MCP tools/call i izolacija (DEMO ONLY)

Ovaj ZIP je **kompletna nadogradnja na v0.8.8**, uključujući sve ranije datoteke. Nema novih SQL migracija, tokena, Client ID vrednosti ili Neon promena. Ne povezuje se pravi Garmin nalog i ne uključuje produkcioni MCP.

## Instalacija — isti postupak

1. Raspakuj ZIP na računar.
2. Kopiraj **sadržaj foldera `public/`** preko odgovarajućeg sadržaja `public/` u GitHub repozitorijumu `zbedic-tron/garminai`. Po potrebi ažuriraj i `render.yaml` (nema nove obavezne izmene Render blueprint-a).
3. GitHub: **Commit changes**. Render: sačekaj uspešan deploy.
4. Otvori `https://garminai-public-demo.onrender.com/healthz` i proveri `version: 0.8.9` i `mode: DEMO_ONLY`.
5. Otvori `https://garminai-public-demo.onrender.com/auth/mcp-oauth/status` i proveri:
   - `mcp_demo_oauth_tools_enabled: true`
   - `mcp_demo_oauth_config_issues: []`
   - `mcp_authenticated_tools_enabled: false`
   - `garmin_live_data_enabled: false`
6. Ako je `mcp_demo_oauth_tools_enabled: false`, u Render > **Environment** proveri već postojeći ključ `GARMINAI_MCP_AUTH_TOOLS_STAGING_ENABLED=1`. Ne dodaj ga duplo. Ako još nije uključen, postavi na `1` i sačuvaj; to je staging-only prekidač.
7. Pokreni **NOVU** autorizaciju na `https://garminai-public-demo.onrender.com/auth/oauth-test` u istoj kartici: Google prijava → Neon Consent → Approve → callback.
8. Očekivani rezultat nakon uspešnog internog MCP testa:

   `PASS: Neon OAuth + PKCE + verified JWT + MCP tools/list and tools/call (status, activities, owned details) + foreign-ID denial. Fictional data only; real MCP/Garmin access disabled.`

Ako se pojavi `PARTIAL PASS`, OAuth je prošao, ali **nije potvrđeno** da su svi MCP pozivi prošli. Pošalji samo tekst završnog statusa i URL-ove `/healthz` i `/auth/mcp-oauth/status` (bez query parametara). Ne šalji token, `code`, `state`, `code_verifier`, potpise, cookie ili Request/Response iz OAuth mrežnog saobraćaja.

## Šta se testira u v0.8.9

- Neon access JWT mora imati važeći potpis, poznati issuer, tačan audience/resource, `openid` scope, poznati Client ID, `at+jwt` i neistekli rok; bez tokena se ne ulazi u MCP. JavaScript test nikada ne vidi JWT.
- Nezavisni staging MCP alat `get_sync_status` se **stvarno poziva** (`tools/call`), a njegov rezultat mora imati `DEMO_ONLY` i `NOT_CONNECTED`.
- `get_activities` se **stvarno poziva** i vraća izmišljene aktivnosti (najviše 10 po pozivu) s identifikatorima vezanim za potpisani `sub`.
- `get_demo_activity_details` se **stvarno poziva** za sopstveni demonstracioni ID. Pokušaj tuđeg/nepostojećeg ID vraća jedinstveno `unknown_demo_activity`, bez odavanja tuđeg ID-a ili postojanja zapisa.
- E2E browser **ne prikazuje** aktivnosti, identitete ni tokene: samo prolaz/neuspeh agregatnih provera.
- Lokalni testovi proveravaju dva različita **kriptografski potpisana** korisnička identiteta, paralelne zahteve, podmetnute ID vrednosti, odbijanje tuđih aktivnosti, odsustvo identity context-a, pogrešan audience, istekao token i ostale ranije zaštite.

## Nove datoteke / ključne izmene

- `public/garminai_public/demo_tenant.py` — samo izmišljeni podaci, procesno privremeni pseudonimni ID-ovi, ne postoji baza identiteta.
- `public/garminai_public/mcp_oauth_gateway.py` — posle verifikacije JWT-a prosleđuje pouzdan identitet kroz **ASGI request scope**, ne kroz HTTP header / JSON-RPC argument. Originalni bearer se uklanja pre poziva MCP alata.
- `public/garminai_public/mcp_oauth_demo.py` — `Context` injekcija MCP 1.x; tri read-only staging alata.
- `public/garminai_public/oauth_e2e_staging.py` — pet nezavisnih pokazatelja: `tools_list`, `get_sync_status`, `get_activities`, `get_demo_activity_details`, `cross_owner_denied`.
- `public/tests/test_mcp_tenant_v089.py` — negativni testovi izolacije korisnika.

**Upozorenje:** Izolacija se odnosi samo na veštačke aktivnosti u demo okruženju. Privremeni ID-ovi se mogu promeniti posle restartovanja/skaliranja, jer se ključ generiše u memoriji procesa. To **nije** produkciono rešenje za privatne podatke. Za realne Garmin naloge biće neophodni trajni identitet, pravila pristupa po resursu, RLS u bazi i end-to-end testovi opoziva tokena. Ovo izdanje ne tvrdi da je ChatGPT dinamički OAuth klijent povezan ili da je produkcioni pristup omogućen.

## Postojeće zaštite ostaju aktivne

- Stari `/mcp` koristi odvojeni DEMO bearer gate, ne menja se.
- `GARMINAI_MCP_OAUTH_STAGING_ENABLED`, `GARMINAI_OAUTH_E2E_STAGING_ENABLED`, `GARMINAI_OAUTH_UI_STAGING_ENABLED` i ostali već podešeni staging prekidači ostaju bez izmene.
- Neon OAuth test klijent i njegova callback URI ostaju kao pre; **ne uključivati `Skip consent`**.
- Nema novih potrebnih environment varijabli, SQL migracija, CORS prečica, isključivanja potpisa, produkcionih Garmin poziva ili skladištenja JWT-a.

## Testiranje i ograničenja

Lokalno: `cd public && python -m unittest discover -s tests -p 'test_*.py' -q`. Browser simulacije: `node tests/js/test_login_flow.cjs tests/js/google_login_v0843.js`, `node tests/js/test_oauth_ui_v086.cjs tests/js/oauth_ui_v086.js`, `node tests/js/test_oauth_e2e_v087.cjs tests/js/oauth_e2e_v087.js`.

Lokalno okruženje nema instaliran paket `mcp` i nema pristup mreži za instalaciju, tako da pravi FastMCP transport **nije** izvršen lokalno. Stvarni E2E test na Render-u obavezan je da potvrdi ponašanje `Context` injekcije i sva četiri `tools/call` zahteva. Pre tog testa nemoj proglašavati MCP v0.8.9 u potpunosti potvrđenim.

## Povratak na v0.8.8

Ako staging test ne radi, postavi `GARMINAI_MCP_AUTH_TOOLS_STAGING_ENABLED=0` u Render Environment i sačuvaj. Time se isključuju novi staging demo alati. Ako treba, vrati prethodni provereni GitHub commit v0.8.8. Nikada ne menjaj produkcione token vrednosti radi ove provere.

Dodatno: `public/docs/V089_MCP_TOOLS_CALL_ISOLATION_SR.md`.
