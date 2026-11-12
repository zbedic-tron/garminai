# GarminAI Public v0.7.1 — OAuth Identity Binding (STAGING)

**Cilj:** povezivanje OAuth pokušaja sa već proverenim korisnikom. Još uvek **nema javnog login-a, Garmin autorizacije uživo niti prijema stvarnih aktivnosti**.

## Šta se menja
- Dodat `garminai_public/oauth_binding.py` — provera VerifiedPrincipal-a na početku i pri callback-u, odbijanje drugog korisnika, jednokratni state.
- Dodati testovi: pogrešan korisnik, replay, istek 10 minuta, odbijena autorizacija, nedostajući code, nema javnog start endpointa.
- `/healthz` izveštava `0.7.1`. Stare demo MCP alatke, literatura i baza ostaju netaknuti.
- **Nema nove SQL migracije**, ne unosi se Garmin Client Secret niti novi key.

## Uputstvo za GitHub i Render
1. Iz ZIP-a kopirati sadržaj `public/` u postojeći `public/` GitHub direktorijum; `render.yaml` ostaje u korenu.
2. Sačekati GitHub commit i Render deploy; otvoriti `/healthz` i potvrditi `0.7.1`.
3. U Render Logs proveriti `GARMINAI_DB_CHECK: PASS (OK)`.
4. `/integration/readiness` treba i dalje da kaže `real_garmin_data_enabled: false`.

## Pre nego što povežemo stvarne korisnike
- Potreban je autentifikacioni sistem koji kreira **pouzdano verifikovan korisnički identitet** i trajnu sesiju. HMAC test-verifikator iz `identity.py` je samo fixture za testove, nikako produkciona prijava.
- Potrebno je implementirati proveru issuer/audience/signature/expiry/scope, otkrivanje OAuth metapodataka i testirati kompletan MCP auth tok.
- Garmin callback mora dobiti već potvrđen identitet iz sigurne sesije; *state sam nije identitet*. Nije dovoljno samo upisati `GARMIN_CLIENT_ID` i `GARMIN_CLIENT_SECRET`.
- Token exchange, šifrovano čuvanje tokena, consent i pouzdana Garmin push isporuka ostaju isključeni.
- Pošto Render Free spava, pouzdanost webhook-ova nije garantovana; pre pilota proveriti retry i garancije isporuke.

**Besplatno:** nema dodatne infrastrukture, nema plaćenog AI API-ja; besplatni planovi imaju limitirana sredstva.
