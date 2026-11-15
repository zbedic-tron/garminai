# GarminAI Public v0.9.2 — stabilizacija privatnog ChatGPT MCP plugina

**0 € dodatnih troškova. Samo demo podaci. Nema Garmin Connect povezivanja ni javnog objavljivanja.**

Ovo je kompletan ZIP zasnovan na ispravnoj verziji v0.9.1. Nema novih besplatnih/plaćenih servisa, SQL migracija, tajnih ključeva, nepoznatih klijenata ili novih OAuth promenljivih. Prethodno povezan **GarminAI MCP** plugin u ChatGPT-u ostaje isti.

## Šta je novo

- Stroga provera isteka access tokena u MCP JWT validaciji: token koji je istekao više nije prihvaćen ni tokom kratkog leeway perioda iz JWT biblioteke. Isti ključ, issuer, audience, scope i dozvoljeni client ID i dalje moraju biti validni.
- Bezbedniji `401 invalid_token` sa `WWW-Authenticate` OAuth discovery i zaglavljem `Cache-Control: no-store`. Nedostupni Neon javni ključevi daju `503 signing_keys_unavailable` i `Retry-After: 5`, bez prolaza u MCP.
- Odbijanje neobično velikih zahteva sa deklarisanim `Content-Length` (pre dodatne provere tokena). To je *preliminarni* guard, ne zamena za eventualna transportna ograničenja.
- Jasniji opisi alata `get_sync_status`, `get_activities` i `get_demo_activity_details` — eksplicitno **fictional/demo**, isključivo read-only. Imena i argumenti ostaju neizmenjeni.
- Simulacija dva potpisana Neon subjekta, paralelni pozivi, odbijanje tuđih ID-jeva, novi validan access token za istog korisnika i nevalidni klijenti/scope/audience.

## Instalacija preko GitHub-a i Rendera

1. Raspakuj ZIP i kopiraj **sadržaj** `public/` u već postojeći `public/` folder repozitorijuma `zbedic-tron/garminai`, uz zamenu izmenjenih fajlova. U korenu ostaje prethodni `render.yaml` (u ovom ZIP-u je takođe prisutan).
2. GitHub **Commit changes**. Render Free treba da uradi standardni deploy.
3. U browseru otvori `https://garminai-public-demo.onrender.com/healthz`. Očekuj `"version":"0.9.2"`, `"mode":"DEMO_ONLY"`, `"garmin_oauth":"NOT_CONNECTED"`.
4. Otvori `https://garminai-public-demo.onrender.com/auth/chatgpt/status`. Proveri `chatgpt_connector_enabled=true` i `chatgpt_config_issues=[]`; URL servera je nepromenjen.
5. Ponovi internu demonstracionu proveru `https://garminai-public-demo.onrender.com/auth/oauth-test` → očekivani stari **PASS** za PKCE, JWT, MCP tools/list i tools/call. Očekivanje nije dokaz da će live test proći.
6. U **postojećem privatnom ChatGPT pluginu GarminAI MCP** izvrši korisničku proveru:
   - „Koristi GarminAI MCP i pozovi `get_sync_status`; jasno reci da li su podaci DEMO_ONLY.“
   - „Pozovi `get_activities`, zatim `get_demo_activity_details` za ID koji je alat vratio. Ne izmišljaj podatke.“
7. Ako ChatGPT zahteva ponovno povezivanje posle isteka tokena, pokreni standardni **Connect** postupak. *Ne* kopiraj access/refresh tokene u ChatGPT poruke, Render logove ili repo.

## Granice potvrde

- Testirano lokalno: Python `unittest` (uključujući simulisane potpisane JWT zahteve za dva korisnika), JS OAuth simulacije.
- **Nije testirano**: stvarni login drugog ChatGPT korisnika, automatsko izdavanje/rotacija refresh tokena kod Neona, ponašanje ChatGPT-a pri isteku tokena i produkcioni MCP transport u ovom lokalnom okruženju bez instaliranog `mcp` SDK-a. Treba proveriti uživo. Nepostojeći dokaz nije PASS.
- Refresh: Neon kao authorization server izdaje/rotira tokene prema svojoj konfiguraciji, ChatGPT je klijent koji može da zatraži novi access token. Naš MCP server *samo proverava* access token svakog zahteva, nema refresh endpoint i ne čuva refresh tokene.
- Izolacija: demonstracioni ID-jevi se menjaju nakon restarta/novog deploy-a; to nije trajna baza Garmin podataka. Tuđi ili zastareli ID je `unknown_demo_activity`, bez otkrivanja tuđih korisnika.
- **Ne koristi ovu staging izolaciju kao dokaz spremnosti za produkcioni višekorisnički sistem.** Potrebna je zasebna proverena implementacija token storage, dozvola, tenant RLS i revizija.

## Provera drugog korisnika — opciono, privatno

Ako ikad imamo dva legitimna testna ChatGPT naloga sa nezavisnim Google/Neon prijavama, svaki može da dobije `get_activities` i obojica mogu uporediti da su prvi demo ID-jevi različiti. Zatim A može da pošalje *samo demo ID* drugom testnom nalogu B; B-ov `get_demo_activity_details` mora da vrati `unknown_demo_activity`. Ne šaljite token, cookie, authorization URL ni bilo šta privatno. Bez dodatnog ili plaćenog naloga samo lokalna simulacija ostaje dovoljno dobar razvojni test, ali ne live potvrda.

## Povratak (rollback)

Ako v0.9.2 ne radi u živom ChatGPT konektoru, vrati kompletan **v0.9.1 ZIP** iz biblioteke u GitHub i uradi Commit → Render deploy. Za momentalno isključivanje ChatGPT staging povezivanja, u Render Environment postavi `GARMINAI_CHATGPT_MCP_STAGING_ENABLED=0` i primeni promenu (stari E2E testni klijent nije obrisan). Ne isključuj validaciju potpisa, OAuth `state`, PKCE, proveru callback-a ili MCP bearer gate.

Detalji: `public/docs/V092_STABILIZATION_SR.md`.
