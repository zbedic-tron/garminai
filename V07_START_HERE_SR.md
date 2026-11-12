# GarminAI Public v0.7 — kratko uputstvo

1. Raspakuj ZIP. **Sadržaj** direktorijuma `public/` prenesi u postojeći GitHub direktorijum `public/` (nikada `public/public/`).
2. `render.yaml` je u korenu repozitorijuma. Ne menjaj postojeći sajt niti GarminAI Windows.
3. Nakon auto-deploy-a potvrdi `/healthz` -> `0.7.0`.
4. U Render Logs proveri `GARMINAI_DB_CHECK: PASS (OK)`.
5. U `/integration/readiness` proveri `real_garmin_data_enabled: false`.
6. Opcionu `sql/002_oauth_pending.sql` NE pokreći dok zajedno ne proverimo deployment. Sledeći korak biće to bezbedno migriranje.

Ne unositi Garmin Client Secret i ne pokušavati vezivanje naloga. Ova verzija dodaje backend za jednokratne OAuth pokušaje, ali nije gotov korisnički OAuth tok.
