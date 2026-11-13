import asyncio
from starlette.requests import Request
from garminai_public.auth_staging_poc import validate_staging_auth_url, staging_login, staging_login_enabled, staging_js

STAGING="https://ep-example-test123.neonauth.c-7.eu-central-1.aws.neon.tech/neondb/auth"

def test_validation():
    assert validate_staging_auth_url(STAGING)
    for url in ["http://x.neon.tech/neondb/auth", "https://evil.example/neondb/auth", "https://user:secret@ep-x.neonauth.c-7.eu-central-1.aws.neon.tech/neondb/auth", "https://ep-x.neonauth.c-7.eu-central-1.aws.neon.tech/neondb/auth?token=x", "https://ep-x.neonauth.c-7.eu-central-1.aws.neon.tech/neondb/auth/../../evil"]:
        assert not validate_staging_auth_url(url), url

def test_disabled_by_default():
    assert not staging_login_enabled({"NEON_AUTH_STAGING_URL":STAGING})
    assert not staging_login_enabled({"NEON_AUTH_STAGING_URL":STAGING,"GARMINAI_STAGING_LOGIN_ENABLED":"true"})
    assert staging_login_enabled({"NEON_AUTH_STAGING_URL":STAGING,"GARMINAI_STAGING_LOGIN_ENABLED":"1"})

def test_disabled_page(monkeypatch):
    monkeypatch.delenv("GARMINAI_STAGING_LOGIN_ENABLED",raising=False)
    req=Request({"type":"http","method":"GET","path":"/auth/staging/google","headers":[]})
    out=asyncio.run(staging_login(req))
    assert b"Test sign-in is disabled" in out.body
    assert b"<script" not in out.body
    assert out.headers["cache-control"].startswith("no-store")
    assert out.headers["x-frame-options"]=="DENY"
    assert asyncio.run(staging_js(req)).status_code == 404

def test_enabled_page_never_claims_mcp_login(monkeypatch):
    monkeypatch.setenv("GARMINAI_STAGING_LOGIN_ENABLED","1")
    monkeypatch.setenv("NEON_AUTH_STAGING_URL",STAGING)
    req=Request({"type":"http","method":"GET","path":"/auth/staging/google","headers":[]})
    out=asyncio.run(staging_login(req))
    assert STAGING.encode() in out.body
    assert b"Continue with Google" in out.body
    assert b"not proof of GarminAI server authorization" in out.body
    js=asyncio.run(staging_js(req))
    assert js.status_code == 200
    assert b"/get-session" in js.body
