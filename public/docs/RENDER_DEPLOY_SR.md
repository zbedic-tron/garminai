# GarminAI Public v0.2 — postavljanje na Render (DEMO)

**PAZNJA: DEMO_ONLY — bez Garmin OAuth, bez autentifikacije, bez stvarnih korisnickih podataka.** Ne unosi licne podatke niti Garmin tokene u repo ili servis.

## 1. Ažuriraj GitHub

U postojećem repozitorijumu `zbedic-tron/garminai` postavi sadržaj ZIP-a:
- `render.yaml` ide u **koren** repozitorijuma (pored `index.html`);
- sadržaj `public/` ide u postojeći direktorijum `public/` (uključujući novi `garminai_public/http_server.py`, ažurirani `requirements.txt` i dokumentaciju).

**Ne praviti** `public/public/`. **Ne brisati** sajt (`index.html`, `style.css`, `privacy.html`, `contact.html`).

## 2. Render

1. Otvori https://dashboard.render.com/ i prijavi se.
2. Izaberi **New > Blueprint**, poveži GitHub nalog i repozitorijum `zbedic-tron/garminai`.
3. Render će pročitati `render.yaml`; proveri **Free** plan, `rootDir: public`, build i start komande, pa potvrdi kreiranje.
4. Sačekaj status **Live** i otvori generisani URL, npr. `https://<stvarni-naziv>.onrender.com/healthz`.
5. Treba da dobiješ JSON sa `"status":"ok"` i `"mode":"DEMO_ONLY"`.
6. MCP endpoint je `https://<stvarni-naziv>.onrender.com/mcp` (ne izmišljaj URL — kopiraj stvarni Render URL).

Ako je Blueprint opcija nedostupna, koristi **New > Web Service** sa istim repozitorijumom: Root Directory `public`, Build `pip install -r requirements.txt`, Start `uvicorn garminai_public.http_server:app --host 0.0.0.0 --port $PORT`, Health Check `/healthz`, instance type **Free**. Render automatski postavlja `RENDER_EXTERNAL_HOSTNAME`; to se koristi kao dozvoljeni Host header. **Ne unosi stvarne Garmin ključeve.**

## 3. Provere

- `https://<hostname>/` prikazuje informativni DEMO JSON.
- `https://<hostname>/healthz` prikazuje status.
- `https://<hostname>/mcp` je MCP, nije obična HTML stranica; otvaranje u browseru ne mora prikazati koristan rezultat.
- Za punu MCP proveru koristi MCP Inspector ili odgovarajućeg klijenta; potvrdi `tools/list` i pozivanje `get_sync_status`.

## 4. Važno o ChatGPT-u

Dostupnost pravljenja prilagođenog MCP plugina u ChatGPT-u zavisi od plana i workspace dozvola. Samo podizanje Render servera NE znači automatski da je alat instaliran ili javno objavljen u ChatGPT-u. U krajnjem slučaju testiraj MCP Inspectorom dok se ne obezbedi podržan način povezivanja.

## 5. Ograničenja

- Ovo je **javni, neautentifikovani DEMO** sa izmišljenim podacima. NIKAD ne uključivati pravi Garmin bez OAuth-a i zaštite pristupa.
- Render Free se uspavljuje posle 15 min bez saobraćaja, ima promenljiv cold-start i efemerni disk. Nije produkciona infrastruktura.
- Literaturu proširuj kontrolisano: komanda `python -m garminai_public.literature_admin --query "..."` predlaže metapodatke iz Crossref-a; studije se prihvataju isključivo posle stručne provere. Kandidati se ne objavljuju korisnicima automatski.
- Proveru zahteva, potpune MCP komunikacije i javnog Render deploy-a treba izvršiti nakon postavljanja. Paket nije već postavljen na hosting.


> UPDATE v0.3: for current instructions see `DEPLOY_V03_SR.md` and `SECURITY_AND_OAUTH_SR.md`. Demo MCP now requires development Bearer token. No real-user OAuth yet.
