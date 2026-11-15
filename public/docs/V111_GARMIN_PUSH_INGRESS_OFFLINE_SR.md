# GarminAI Public v1.1.1 — Garmin push ingress: priprema, bez live prijema

## Najvažnije: stvarni push je i dalje ISKLJUČEN

**Ne unosi nove adrese u Garmin API Tools i ne čekiraj `Enabled`.**
`POST /garmin/push/*` vraća `503` i ne čita sadržaj zahteva.
Garmin OAuth povezivanje ostaje aktivno; ChatGPT MCP čita samo demo aktivnosti.

## Šta je dokazano dokumentacijom (poverljivi partner materijal)

Activity API 2.1 navodi HTTPS POST sa JSON telom, rok od 30 sekundi, 200 OK kao potvrdu dostave, ponovne pokušaje i `On Hold` mehanizam. U materijalu je naveden i spisak izvorišnih IP mreža. **Nijedna stvarna Garmin IP adresa niti partner primeri nisu kopirani u javni kod ili ovaj dokument.**

Posebno je važno: dokument ne opisuje HMAC/mTLS potpis po zahtevu. CIDR podudaranje nije kriptografska potvrda porekla. Kada je Render proxy između pošiljaoca i aplikacije, direktna socket IP adresa pripada proxy-ju; `X-Forwarded-For` se ne sme samostalno smatrati proverljivim dokazom porekla. Render Free ne omogućava platformsku ingress IP allowlistu za web servise.

## Sadržaj v1.1.1

- `garmin_sender_review_v111.py`: čista offline evaluacija ASGI peer adrese i proxy zaglavlja. Nikada ne autorizuje javni webhook. IP mreže se dostavljaju isključivo kao lokalni test ulaz i ne sadrže Garminove poverljive mreže.
- `garmin_push_inbox_v111.py`: dodatak za offline upis **sintetičkih, minimalnih JSON sažetaka** u trajni inbox. Zahteva verified Neon subject i Garmin user link iz baze, transakciju, jedinstveni `(subject, activity_id)`, odbijanje konflikata i upis bez tokena/GPS-a.
- `sql/005_garmin_push_inbox_offline.sql`: nova RLS tabela; `garminai_app` samo SELECT i INSERT; brisanje preko FK cascade kada se ukloni korisnik.
- Model potvrde prijema u offline testovima: HTTP 200 tek nakon dokazano pouzdanog ingress konteksta, potvrđenog vlasništva, validne poruke i **trajnog prihvatanja u inbox**. Dalja obrada aktivnosti mora biti zasebna. Ovaj model **nije** spojen na javni HTTP endpoint.

## Instalacija

1. Razpakuj delta ZIP v1.1.1 i kopiraj samo sadržaj `public/` preko postojećeg `public/` u GitHub-u; commit.
2. Render nakon deploy-a: `/healthz` prikazuje `1.1.1`; `/garmin/integration/status` potvrđuje `verified_live_ingress_enabled=false`, `push_ingestion_enabled=false`, `mcp_real_garmin_data_enabled=false`.
3. Neon SQL Editor → ista grana i baza kao Render, vlasnik šeme: izvrši `public/sql/005_garmin_push_inbox_offline.sql`.
4. Render Logs: `GARMINAI_DB_CHECK: PASS (OK)` nakon eventualnog ponovnog deploy-a. Provera je read-only i nova tabela je opciona pre migracije.
5. Ako se ponovi problem iz v1.0.1, prvo proveri da li Render `DATABASE_URL` odgovara Neon grani. Ne menjaj ga naslepo.

Provera Neon RLS i privilegija:

```sql
SELECT c.relname AS table_name, c.relrowsecurity AS rls_enabled,
       c.relforcerowsecurity AS force_rls,
       has_table_privilege('garminai_app', c.oid, 'SELECT') AS can_select,
       has_table_privilege('garminai_app', c.oid, 'INSERT') AS can_insert,
       has_table_privilege('garminai_app', c.oid, 'UPDATE') AS can_update,
       has_table_privilege('garminai_app', c.oid, 'DELETE') AS can_delete
FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'garminai' AND c.relname = 'garmin_push_inbox';
```

Očekivano: `t, t, t, t, f, f` nakon imena tabele. Testi koriste lažnu bazu, ne pravi Garmin nalog.

## Granice i uslovi pre stvarnog prijema

1. **Verifikacija na ingress-u:** nezavisno dokumentovan i proverljiv izvorni IP kroz Render edge ili drugi odgovarajući mehanizam, i dalje bez troškova; tek tada kompletan end-to-end test protiv spoofing-a.
2. **Trajni ACK:** po prijemu dokazano autentične poruke, minimalan validirani inbox upis, onda `200 OK`, pa zasebna obrada. Fail closed sa non-200 omogućava Garmin retry; uskladiti sa realnom brzinom i ponašanjem Render Free.
3. **Deregistration/permissions:** implementirati odvojenu proveru dozvola, brisanje, retention i recovery pre javnog rada.
4. **Ugovor i AI:** Garmin Connect Developer License Agreement Rev H, posebno 5.2 i 15.10–15.11, ograničava deljenje podataka sa trećim stranama i AI. Korisnička saglasnost sama po sebi nije dovoljna. Ne slati stvarne Garmin podatke ChatGPT-u, čak ni izvedene sažetke, dok odgovarajuće ovlašćenje nije razjašnjeno.
5. **0 €:** bez novih usluga, enterprise funkcija, naplate API-ja ili javne objave bez izričitog dogovora.

## Rollback

Vrati samo izmenjene Python datoteke u v1.1.0. Tabelu `garmin_push_inbox` možeš ostaviti praznu i pod RLS; ne briši postojeće podatke ili Garmin OAuth povezivanje. Nikada ne vraćaj stvarni push u prethodno zaključan endpoint.
