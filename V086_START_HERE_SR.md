# GarminAI Public v0.8.6 — IDemo! 🚀

NOVA VERZIJA: **OAuth Login & Consent staging UI**.

**Prvo uradi samo deploy; ne uključuj OAuth.**

1. Raspakuj ovaj ZIP.
2. Kopiraj sadržaj `public/` u postojeći GitHub `public/` repo `zbedic-tron/garminai` i uradi Commit changes.
3. Sačekaj automatski Render deploy (ne treba menjati Environment).
4. Proveri:
   - `https://garminai-public-demo.onrender.com/healthz` — verzija `0.8.6`.
   - `https://garminai-public-demo.onrender.com/auth/oauth-ui/status` — `oauth_ui_staging_enabled` = `false`.
5. Javi rezultat dve provere. Zatim radimo Neon OAuth Provider test u **auth-staging** grani, uz posebno odobrenje pre aktiviranja.

Nova promenljiva `GARMINAI_OAUTH_UI_STAGING_ENABLED` ostaje nepostavljena ili `0`.

Nema SQL migracija. Nema novih Python biblioteka. Nema Garmin API promena. Nema promena privatnog GarminAI Windows projekta. Šest postojećih demo MCP alatki nije dirano.

DOKUMENTACIJA: `public/docs/V086_OAUTH_LOGIN_CONSENT_SR.md`.

TESTOVI (iz `public/`):

    python -m unittest discover -s tests -p 'test_*.py' -q
    node tests/js/test_oauth_ui_v086.cjs tests/js/oauth_ui_v086.js

Ne mešati uslovnu UI implementaciju sa aktivnim OAuth-om: OAuth Provider i MCP pristup su i dalje isključeni.
