# GarminAI Public v0.8.7 — kontrolisani Neon OAuth E2E test

**Datum:** 2026-11-15. **Status:** lokalno testirano; stvarni Neon/ChatGPT OAuth tok NIJE potvrđen.

## Šta je implementirano

- Nezavisni, podrazumevano isključeni **testni javni OAuth klijent** na `/auth/oauth-test` (bez client secret-a).
- PKCE/S256 (nasumični verifier i challenge), `state`, zasebna tačna povratna adresa `/auth/oauth-test/callback`, kontrola odgovora `iss` i najviše 10 minuta trajanja pokušaja.
- Callback briše `code`, `state`, `iss` iz browser URL-a pre obrade; kod se ne prikazuje na stranici i ne upisuje u localStorage, konzolu ili Render logove iz aplikacije.
- Izdvojeni server-side POST `/auth/oauth-test/exchange` šalje kod i PKCE verifier SAMO na fiksni `NEON_AUTH_STAGING_URL` `/oauth2/token`; bez client secret-a, redirect-a i promenljivih eksternih hostova.
- Provera JWKS/kriptografskog potpisa, `typ=at+jwt`, `iss`, `aud`, `exp`, `iat`, `scope=openid`, `azp` tačnog testnog klijenta; podržani su RS256, EdDSA i ES256. Token se ne skladišti niti vraća korisniku.
- Odbijeni, duplirani, istekli ili promenjeni callback-i ostaju bez pristupa. Namerno nemamo dugme za upotrebu tokena u MCP-u.
- Stranice: CSP `frame-ancestors 'none'`, `no-store`, `no-referrer`; endpoint za razmenu ograničen na isti browser origin, JSON i male zahteve; procesno ograničenje zahteva na Neon endpoint.
- `/mcp` ostaje demo gate; Garmin API, stvarni Garmin podaci i AI consent nisu uključeni. Bez dodatnih SQL tabela i bez promena Windows GarminAI.

## 1. Postavljanje (pre konfigurisanja klijenta)

Prenesi **sadržaj** ZIP `public/` u GitHub `zbedic-tron/garminai` `public/`, pa commit. Korenski `render.yaml` se nije menjao.

Potvrdi:
- `https://garminai-public-demo.onrender.com/healthz` → `version:0.8.7`, `mode:DEMO_ONLY`;
- `https://garminai-public-demo.onrender.com/auth/oauth-test/status` → `oauth_e2e_test_enabled:false` (očekivano).

Ne menjaj tekuće `DATABASE_URL`, `NEON_AUTH_URL`, Garmin Developer credentials ni produkcionu Neon granu.

## 2. Neophodno pre stvarnog testa: testni javni OAuth klijent u Neon Console

U Neon projekat `garminai-public` → **auth-staging** → Better Auth → OAuth provider → **OAuth clients → Create client**. Unesi, ako UI izlaže ta polja:

| Polje | Vrednost |
|---|---|
| Client name | GarminAI OAuth E2E Test |
| Client type / Token endpoint authentication | **Public** / **none** (BEZ client secret-a) |
| Application type | **Web** |
| Redirect URI (tačno) | `https://garminai-public-demo.onrender.com/auth/oauth-test/callback` |
| Allowed scopes | samo `openid` |
| Grant | `authorization_code` |
| Allowed / linked resource | `https://garminai-public-demo.onrender.com/mcp-oauth-staging` |
| Skip consent | **No / off** |
| PKCE | **required, S256** |

**Ne koristi** `client_secret_basic`, `offline_access`, `profile`, `email` ili stvarni Garmin resource. Ne kreiraj klijenta u `production` grani. Ako UI nema opciju za vezivanje resursa ili za javnog klijenta, ZAUSTAVI podešavanje i pošalji snimak polja; ne zaobilazi `invalid_target` i ne uključuj DCR bez potrebe.

Sačuvaj samo **javni Client ID** (nije lozinka); novi client secret ne bi smeo da se generiše u public režimu. Ako se generiše, klijent nije podešen kao javni, nemoj taj secret stavljati u Render.

## 3. Render env — tek kada postoji javni testni client ID

Zadrži već potvrđene staging konfiguracije:
- `GARMINAI_MCP_OAUTH_STAGING_ENABLED=1`
- `GARMINAI_MCP_OAUTH_STAGING_ISSUER=<Neon auth-staging issuer iz discovery>`
- `NEON_AUTH_STAGING_URL=<isti issuer>`
- `GARMINAI_OAUTH_UI_STAGING_ENABLED=1`
- `GARMINAI_STAGING_LOGIN_ENABLED=0` (stara stranica se ne koristi).

Dodaj samo:

```
GARMINAI_OAUTH_TEST_CLIENT_ID=<PUBLIC CLIENT ID IZ NEON-A>
GARMINAI_OAUTH_E2E_STAGING_ENABLED=1
```

Nakon redeploy-a: `/auth/oauth-test/status` → `oauth_e2e_test_enabled:true` i `configuration_issues:[]`.

## 4. Kontrolisani E2E test

1. Otvori `https://garminai-public-demo.onrender.com/auth/oauth-test` u **istoj kartici** tokom celog postupka; klikni **Start OAuth test**.
2. Neon `/oauth2/authorize` mora prihvatiti `response_type=code`, `openid`, PKCE/S256, registrovani resurs i callback.
3. Neon usmerava na postojeći `/auth/login`, pa `/auth/consent` sa **potpisanim** `oauth_query`. **Važno:** v0.8.6 UI je fail-closed dok Neon ne podrži `/oauth2/public-client-prelogin`; ova v0.8.7 nadogradnja ne menja taj uslov.
4. Google sign-in, pa eksplicitno Approve ili Deny. Ne deli snimke ili URL koji sadrže `sig`, `oauth_query`, `neon_auth_session_verifier`, `code`, `state` ili tokene.
5. Approve → Neon vraća `code`, `state`, `iss` na naš callback. Na serveru se kod razmenjuje i access JWT potvrđuje. Uspeh se pojavljuje kao `PASS: authorization code exchanged...`, **bez prikaza tokena**. Deny → `Consent denied by user` i bez zamene koda.
6. Čak i pri PASS, korisničke MCP alatke i Garmin podaci **ostaju isključeni**. Ovo NIJE pun ChatGPT OAuth test.

Ako se pojavi `HTTP_403` ili `HTTP_404` na prelogin, problem može biti managed Neon opcija `allowPublicClientPrelogin`. Nemoj zameniti taj korak verovanjem potpisu iz URL-a. Ako endpoint ne postoji, treba pripremiti zasebnu bezbednu prilagodbu Login/Consent stranice.

Ako Neon odbije token sa `invalid_target`, proveri linkovanje javnog klijenta i resource u Neon Console. Ako server prijavi `ACCESS_TOKEN_NOT_JWT`, ne tretiraj kao PASS — resurs mora izdavati JWT pogodan za našu kasniju bezbednu MCP verifikaciju. Ako `JWT_TYPE_INVALID` ili `JWT_CLAIMS_INVALID`, proverićemo stvaran format odgovora bez deljenja tokena.

## 5. Posle testa

Vrati `GARMINAI_OAUTH_E2E_STAGING_ENABLED=0`. Ako završimo test i više ne koristimo UI, vrati i `GARMINAI_OAUTH_UI_STAGING_ENABLED=0`. Neon testnog OAuth klijenta možeš disable-ovati bez brisanja. **Nikada ne uključuj** pristup stvarnim Garmin podacima na osnovu ovog smoke testa.

## Bezbednosne i testne granice

- Testni endpoint javno prima validne authorization code + verifier parove dok je prekidač 1. Ne koristi ga na produkciji; ostaje ograničen na poznat host i jedan javni testni klijent. Procesni limiter nije distribuirani zaštitni zid.
- Token se kratkotrajno obrađuje u serverskoj memoriji zbog provere, nikada ne čuva ili šalje nazad. HTTP `code` dolazi u URL-u callback-a po standardnom Authorization Code flow-u; stranica ga odmah uklanja iz address bara.
- Testovi koriste izmišljene jwt ključeve i browser simulaciju. Nema pravog Google / Neon izdavanja tokena u lokalnim testovima.
- Potrebna zasebna validacija stvarnog provider login/consent toka, registracije klijenta i resursa, stvarnog JWT formata, OpenAI MCP klijenta i RLS izolacije pre daljeg rada.

Izvori (javna dokumentacija):
- https://better-auth.com/docs/plugins/oauth-provider/clients
- https://better-auth.com/docs/plugins/oauth-provider/tokens
- https://better-auth.com/docs/plugins/oauth-provider/sign-in-flow
- https://github.com/neondatabase/neon-js/blob/main/packages/auth/README.md
