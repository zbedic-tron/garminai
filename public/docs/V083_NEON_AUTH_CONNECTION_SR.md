# GarminAI Public v0.8.3 — Neon Auth proveravanje (bezbedni staging)

## Šta postoji
- Konfiguraciona promenljiva `NEON_AUTH_URL` (javni Neon Auth base URL za *production* granu, bez lozinke).
- Stroga provera HTTPS i Neon auth hostname-a.
- Server pri pokretanju šalje **neautentifikovani GET** na `/get-session`; ne čita odgovor i ne prosleđuje cookies, tokene ili korisničke podatke.
- Zapis u Render Logs: `GARMINAI_NEON_AUTH_CHECK: PASS (REACHABLE_UNAUTHENTICATED)` ili `FAIL (KOD)`.
- `auth/development-status` prikazuje samo da li je URL konfigurisan i strukturno ispravan. Nije dokaz OAuth funkcionalnosti.
- Login/consent stranice ostaju namerno onemogućene; svih šest MCP alatki rade samo sa izmišljenim aktivnostima.

## Zašto se još ne prijavljujemo
Neon Managed Better Auth je OAuth 2.1 autorizacioni server, ali za stvarni tok još treba implementirati službeni Neon klijent i čuvanje/verifikaciju sesije, potpisani oauth_query i MCP zaštićeni resurs (401 + metadata). *OAuth Provider se ne uključuje dok to nije završeno.*

## Postavljanje
1. Kopiraj sadržaj `public/` u postojeći `public/` na GitHub-u; `render.yaml` ostaje u korenu.
2. Proveri `/healthz` -> `0.8.3` i `GARMINAI_DB_CHECK: PASS (OK)`.
3. U Neon Settings > Better Auth kopiraj vrednost **Auth URL** (nije JWKS URL i nije DATABASE_URL).
4. U Render Environment dodaj `NEON_AUTH_URL` sa celom vrednošću, npr. `https://ep-....neonauth.c-7.eu-central-1.aws.neon.tech/neondb/auth`.
5. Save, rebuild and deploy. U Render Logs filtriraj `GARMINAI_NEON_AUTH_CHECK`.
6. Ako je FAIL, prijavi samo *kod statusa* (bez URL-a, tokena ili kredencijala).

**Bez Google login/consent aktivacije, bez Garmin aktivnosti i dodatne baze.** Postojeće Windows GarminAI ne menjati.
