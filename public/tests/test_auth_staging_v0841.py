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

def test_only_known_google_host_allowed():
    assert 'u.hostname !== "accounts.google.com"' in _JS
    assert 'location.assign(dest)' in _JS
