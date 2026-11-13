from garminai_public.auth_staging_poc import _JS

def test_social_sign_in_uses_explicit_json_no_redirect():
    assert 'disableRedirect:true' in _JS
    assert 'redirect:"error"' in _JS
    assert 'provider:"google"' in _JS

def test_diagnostics_are_categorized_and_never_show_raw_messages():
    assert 'safeErrorCode' in _JS
    assert 'NETWORK_OR_CORS' in _JS
    assert 'HTTP_' in _JS
    assert 'setStatus("Sign-in start failed [" + safeErrorCode(e)' in _JS

def test_only_configured_neon_init_or_known_google_authorization_allowed():
    assert 'u.origin === authBase.origin' in _JS
    assert 'u.pathname === authBase.pathname + "/sign-in/social/init"' in _JS
    assert 'u.searchParams.size === 1' in _JS
    assert 'u.searchParams.get("token")' in _JS
    assert 'u.origin === "https://accounts.google.com"' in _JS
    assert 'if (!neonInit && !googleAuthorize) throw Error("INVALID_DESTINATION")' in _JS
    assert 'location.assign(u.href)' in _JS


def test_no_token_leak_in_ui():
    assert 'status.textContent = s' in _JS
    assert 'No token is displayed, logged or stored by this page.' in _JS
    assert 'console.log' not in _JS
