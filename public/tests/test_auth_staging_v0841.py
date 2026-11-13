"""Regression checks kept from v0.8.4.1 and updated for v0.8.4.3."""
from garminai_public.auth_staging_poc import _JS


def test_social_sign_in_uses_json_no_redirect():
    assert 'disableRedirect: true' in _JS
    assert 'redirect: "error"' in _JS
    assert 'provider: "google"' in _JS


def test_diagnostics_are_categorized_and_no_raw_messages():
    assert 'safeErrorCode' in _JS
    assert 'NETWORK_OR_BROWSER_POLICY' in _JS
    assert 'HTTP_' in _JS
    assert 'setStatus("Sign-in start failed [" + safeErrorCode(error)' in _JS
    assert 'result?.user ?? result?.data?.user' in _JS


def test_only_configured_neon_init_or_known_google_authorization_allowed():
    assert 'next.origin === authBase.origin' in _JS
    assert 'next.pathname === authBase.pathname + "/sign-in/social/init"' in _JS
    assert 'next.searchParams.size === 1' in _JS
    assert 'next.searchParams.get("token")' in _JS
    assert 'next.origin === "https://accounts.google.com"' in _JS
    assert 'if (!neonInit && !googleAuthorize) throw Error("INVALID_DESTINATION")' in _JS
    assert 'location.assign(next.href)' in _JS


def test_no_token_leak_in_ui():
    assert 'status.textContent = value' in _JS
    assert 'never a token or a user ID' in _JS
    assert 'console.log' not in _JS
