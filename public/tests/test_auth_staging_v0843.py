"""Verifer exchange invariants (runtime checked by tests/js/test_login_flow.cjs)."""
from garminai_public.auth_staging_poc import _JS
from pathlib import Path


def test_verifier_is_captured_before_query_is_removed():
    capture = _JS.index('callbackParams.get("neon_auth_session_verifier")')
    clear = _JS.index('history.replaceState(')
    assert capture < clear


def test_verifier_only_sent_to_neon_get_session():
    assert '"/get-session?neon_auth_session_verifier="' in _JS
    assert 'encodeURIComponent(oneTimeVerifier)' in _JS
    assert 'await checkSession(verifier)' in _JS
    assert 'getAll("neon_auth_session_verifier").length === 1' in _JS


def test_no_callback_with_missing_or_expired_pending_marker():
    assert 'sessionStorage.getItem(PENDING_KEY)' in _JS
    assert 'Date.now() - timestamp > MAX_PENDING_MS' in _JS
    assert 'clearPending();' in _JS
    assert 'BROWSER_STORAGE_UNAVAILABLE' in _JS


def test_null_session_is_not_network_error():
    assert 'result?.user' in _JS
    assert 'result?.session' in _JS
    assert 'No active Neon session found in this browser.' in _JS
    assert 'NETWORK_OR_CORS' not in _JS


def test_missing_production_authorization_and_fixed_version():
    source = Path(__file__).resolve().parents[1] / 'garminai_public' / 'http_server.py'
    text = source.read_text()
    assert text.count('"version":"0.8.5"') == 2
    assert '"version":"0.8.4.1"' not in text
    assert 'DEMO_ONLY' in text
    assert 'DemoBearerGate' in text
