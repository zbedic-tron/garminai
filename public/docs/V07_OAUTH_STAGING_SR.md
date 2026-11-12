# GarminAI Public v0.7 — OAuth Identity & Pending Authorization (STAGING)

## Granice verzije
- 6 demo MCP alatki i `/mcp` sa razvojnim Bearer tokenom rade kao ranije.
- **NEMA** javnog Garmin Connect dugmeta, produkcionog korisničkog prijavljivanja, prijema Garmin push poruka niti analize stvarnih korisničkih aktivnosti.
- Kod za **kratkotrajne OAuth pokušaje** je pripremljen i nije priključen na javne rute.
- `GARMIN_CLIENT_ID`, `GARMIN_CLIENT_SECRET`, Garmin tokeni i šifarski ključevi se **ne** dodaju u Render u ovoj fazi.

## Zašto dva OAuth toka?
1. ChatGPT/MCP OAuth 2.1: korisnik se prijavljuje na nezavisan identitetski servis GarminAI; server proverava `issuer`, `audience`, `exp`, `scope` svakog zahteva.
2. Garmin OAuth 2.0 + PKCE: već prijavljeni GarminAI korisnik daje Garmin dozvolu; sačuva se mapiranje njegovog internog identiteta na Garmin `userId`.
Garmin `state` NIJE prijava korisnika. Bez pouzdane veze sa već proverenim korisnikom callback se mora odbiti.

## SQLite/Neon/Render
- Ne čuvati OAuth attempts u RAM-u jer Render Free uspavljuje i restartuje instancu.
- `sql/002_oauth_pending.sql` (opciono): kreira `garminai.oauth_attempts`, RLS, TTL i ograničene dozvole za garminai_app. Pokrenuti ručno samo uz postojeću 001 šemu i testiran `garminai_app`.
- Držati tajni 32-bajtni AES-GCM ključ van GitHub-a; **ne podešavati još** dok ne implementiramo stvarni tok.
- `PendingOAuthStore.begin()` vraća URL i state, čuva samo SHA-256(state) i šifrovan PKCE verifier; `consume()` briše zapis atomski. Pokušaji ističu nakon 10 min; istekle zapise naknadno treba čistiti kontrolisanom procedurom.
- Bez proverenog identiteta nikada ne pozivati ove metode u produkciji.

## Pre prvog pravog Garmin naloga
1. Izabrati usklađen, besplatan identitetski servis za ChatGPT/MCP ili razviti potpuno provereno OAuth 2.1 rešenje, uz objavljivanje discovery metapodataka i PKCE.
2. Dodati sigurne cookie sesije ili ekvivalent koji vezuje callback za originalnog prijavljenog korisnika.
3. Implementirati proveru state, jednokratni consume, proveru grešaka callback-a, exchange tokena i verifikaciju Garmin userId.
4. Sačuvati refresh/access tokene šifrovano i vezati ih za ispravan subject.
5. Verifikovati tačan Activity API push format i autentičnost isporuke u Garmin Portalu, urediti retry/idempotency i sigurno skladištenje.
6. Integrisati izričitu korisničku saglasnost za AI uz Garminovu dozvolu, bez korišćenja Garmin podataka za treniranje/evaluaciju AI modela.
7. Potvrditi troškove, limits, obradu podataka i dostupnost ChatGPT plugin-a za ciljne korisnike.

## Redosled na GitHub/Render
1. Ažurirati samo sadržaj `public/` i korenski `render.yaml`, bez `public/public/`.
2. `/healthz` treba da kaže `0.7.0`, a `/integration/readiness` i dalje `real_garmin_data_enabled: false`.
3. `GARMINAI_DB_CHECK: PASS (OK)` u Render Logs treba da ostane; DB checker podržava postojeće 4 tabele i opcionu petu.
4. SQL migraciju 002 primeniti tek u narednom koraku, uz proveru da schema i politika postoje; ne kopirati lozinke u chat.

## Važno o besplatnom radu
Cilj je 0 EUR, ali Render Free cold-start može usporiti/neuspeti Garmin push isporuku. Garmin Starter nema istorijski backfill. Ne obećavati korisnicima analizu istorije odmah po povezivanju niti produkcionu dostupnost bez provere push isporuke.
