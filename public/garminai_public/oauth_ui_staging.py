"""v0.8.6: opt-in, staging-only Neon-managed OAuth login/consent browser pages.

Neon is ALWAYS the authorization server. These pages MUST NOT sign requests,
issue tokens, verify identities for MCP, or decide authorization themselves.
The /oauth2/public-client-prelogin call verifies Neon's signed oauth_query
before the page reveals client details or enables any consent action.

IMPORTANT: Neon OAuth Provider's allowPublicClientPrelogin option must be enabled
by the operator *when* testing the real flow. Without it, UI fails closed.
No real Garmin data or MCP tool authorization is enabled by these pages.
"""
import os
import re
from html import escape
from urllib.parse import urlsplit

from starlette.responses import HTMLResponse, JSONResponse, Response
from .auth_pages import login_page as disabled_login, consent_page as disabled_consent
from .auth_staging_poc import validate_staging_auth_url

_HOST = re.compile(r"^(?=.{1,253}$)[a-z0-9](?:[a-z0-9.-]*[a-z0-9])$")


def configuration(env=None):
    e = os.environ if env is None else env
    enabled = e.get("GARMINAI_OAUTH_UI_STAGING_ENABLED") == "1"
    base = e.get("NEON_AUTH_STAGING_URL", "").strip()
    hostname = e.get("RENDER_EXTERNAL_HOSTNAME", "").strip().lower()
    issues = []
    if not validate_staging_auth_url(base):
        issues.append("INVALID_STAGING_AUTH_URL")
    if not _HOST.fullmatch(hostname) or ".." in hostname or hostname.endswith("."):
        issues.append("INVALID_EXTERNAL_HOST")
    # Do not allow an accidentally enabled staging UI on a custom production host.
    if hostname and not hostname.endswith(".onrender.com"):
        issues.append("UNEXPECTED_STAGING_HOST")
    return {
        "enabled": bool(enabled and not issues),
        "requested": enabled,
        "issues": issues,
        "neon_auth": base if enabled and not issues else "",
        "resource": "https://" + hostname + "/mcp-oauth-staging" if enabled and not issues else "",
    }


_CSS = """
:root{font:16px system-ui,-apple-system,'Segoe UI',sans-serif;color-scheme:dark}
*{box-sizing:border-box} body{background:#0b1220;color:#f3f7fa;min-height:100vh;display:grid;place-items:center;margin:0;padding:20px}
main{width:min(650px,100%);border-radius:18px;border:1px solid #324155;background:#142133;padding:30px}
.brand{color:#76ead4;font-weight:750;letter-spacing:.04em}p,li{color:#d2dfed;line-height:1.55}
.notice{background:#292a33;border-left:4px solid #f0b85a;border-radius:5px;padding:14px}
button{border:1px solid #7ee6d2;border-radius:10px;background:#157763;color:white;min-height:44px;padding:10px 18px;cursor:pointer;margin:4px 6px 4px 0}
button.deny{background:#4c2935;border-color:#f7b4b4}button:disabled{background:#344255;color:#b8c5d3;cursor:not-allowed;border-color:#596979}
#status{min-height:2em}#client, #rights{background:#1a3042;padding:12px;border-radius:7px;overflow-wrap:anywhere}
#client p,#rights p{margin:4px 0}a{color:#76ead4}footer{margin-top:28px;border-top:1px solid #33475c;padding-top:14px;color:#9fb3ca;font-size:13px}
"""


def _response(*, mode: str, base: str, resource: str) -> HTMLResponse:
    # Only operator-controlled values appear in markup. OAuth URL/query is NEVER echoed.
    title = "Sign in to GarminAI" if mode == "login" else "Authorize ChatGPT / MCP"
    if mode == "login":
        controls = '<button type="button" id="signin" disabled>Continue with Google (test)</button>'
    else:
        controls = ('<div id="client" hidden><strong id="client-name"></strong><p id="client-host"></p></div>'
                    '<div id="rights" hidden><strong>Requested permissions</strong><p id="scope"></p><p id="resource"></p></div>'
                    '<button type="button" id="allow" disabled>Approve</button>'
                    '<button type="button" id="deny" class="deny" disabled>Deny</button>'
                    '<a id="login-link" hidden href="/auth/login">Sign in first</a>')
    html = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(title)}</title><style>{_CSS}</style></head>
<body><main data-mode="{mode}" data-auth="{escape(base, quote=True)}" data-resource="{escape(resource, quote=True)}">
<div class="brand">GARMINAI PUBLIC · OAUTH STAGING</div><h1>{escape(title)}</h1>
<p class="notice">Staging only. This page never connects Garmin accounts or grants MCP tool access.</p>
{controls}<p role="status" aria-live="polite" id="status">Verifying signed request with Neon…</p>
<footer>Neon validates the signed request and consent. Never approve unknown apps. Garmin Connect authorization is a separate step.</footer>
</main><script defer src="/auth/oauth-ui.js"></script></body></html>'''
    origin = urlsplit(base).scheme + "://" + urlsplit(base).netloc
    csp = ("default-src 'none'; base-uri 'none'; object-src 'none'; frame-ancestors 'none'; "
           "style-src 'unsafe-inline'; script-src 'self'; connect-src " + origin + "; form-action 'none'")
    headers = {"Cache-Control":"no-store, max-age=0", "Pragma":"no-cache",
               "Referrer-Policy":"no-referrer", "X-Content-Type-Options":"nosniff",
               "X-Frame-Options":"DENY", "Content-Security-Policy":csp,
               "Permissions-Policy":"camera=(), microphone=(), geolocation=()"}
    return HTMLResponse(html, headers=headers)


async def login_page(request):
    c = configuration()
    if not c["enabled"]:
        return await disabled_login(request)
    return _response(mode="login", base=c["neon_auth"], resource=c["resource"])


async def consent_page(request):
    c = configuration()
    if not c["enabled"]:
        return await disabled_consent(request)
    return _response(mode="consent", base=c["neon_auth"], resource=c["resource"])


async def ui_status(request):
    c = configuration()
    return JSONResponse({
        "version":"0.8.6", "mode":"STAGING_ONLY",
        "oauth_ui_staging_enabled": c["enabled"],
        "oauth_ui_config_errors": c["issues"] if c["requested"] else [],
        "provider_enabled_by_this_app": False,
        "mcp_authenticated_tools_enabled": False,
        "garmin_live_data_enabled": False,
        "next":"Verify Neon OAuth Provider public-client-prelogin, issuer, signing and callback in a controlled test before enabling OAuth flow.",
    }, headers={"Cache-Control":"no-store"})


_JS = r'''"use strict";
// v0.8.6: signed OAuth request staging. No MCP tokens, Garmin data or client secrets.
// See docs/V086_OAUTH_LOGIN_CONSENT_SR.md for provider configuration requirements.
(() => {
  const root = document.querySelector('main[data-mode]');
  if (!root) return;
  const mode = root.dataset.mode;
  const base = root.dataset.auth;
  const resource = root.dataset.resource;
  const status = document.getElementById('status');
  const signin = document.getElementById('signin');
  const allow = document.getElementById('allow');
  const deny = document.getElementById('deny');
  const pendingKey = 'garminai.oauth-ui-staging.pending.v1';
  const maxAgeMs = 10 * 60 * 1000;
  let busy = false;
  const note = message => { status.textContent = message; };
  const disableAll = () => { for (const b of [signin, allow, deny]) if (b) b.disabled = true; };

  // Only the parameters designated by the provider's signed ba_param list are
  // forwarded. The session verifier is NOT part of oauth_query.
  function signedRequest(params) {
    const names = params.getAll('ba_param');
    if (params.getAll('sig').length !== 1 || names.length < 1 || names.length > 48 ||
        names.some(n => !/^[a-zA-Z][a-zA-Z0-9_]{0,63}$/.test(n)) ||
        params.getAll('client_id').length !== 1 || params.toString().length > 8192) return null;
    const keys = new Set(['sig', 'ba_param', ...names]);
    if (![...keys].every(k => k === 'sig' || k === 'ba_param' || names.includes(k))) return null;
    const query = new URLSearchParams([...params].filter(([key]) => keys.has(key)));
    if (!query.has('client_id') || !query.has('sig')) return null;
    return query;
  }

  const params = new URLSearchParams(location.search);
  const verifier = params.get('neon_auth_session_verifier');
  const hasVerifier = params.has('neon_auth_session_verifier');
  const signed = signedRequest(params);
  // Strip the session verifier and any unrelated parameters from the address.
  if (signed) history.replaceState(null, '', location.pathname + '?' + signed.toString());
  else if (location.search) history.replaceState(null, '', location.pathname);

  function usableRedirect(value, {neonOnly = false} = {}) {
    if (typeof value !== 'string' || value.length > 4096) return null;
    let u;
    try { u = new URL(value); } catch (_) { return null; }
    if (u.protocol !== 'https:' || u.username || u.password || u.hash) return null;
    if (neonOnly) {
      const auth = new URL(base);
      if (u.origin !== auth.origin || u.pathname !== auth.pathname + '/sign-in/social/init' ||
          u.searchParams.size !== 1 || !/^[A-Za-z0-9_-]{16,256}$/.test(u.searchParams.get('token') || '')) return null;
    }
    return u.href;
  }

  async function api(path, {method = 'GET', body = undefined} = {}) {
    let res;
    try {
      res = await fetch(base + path, {
        method, credentials:'include', mode:'cors', redirect:'error', cache:'no-store',
        headers: {'Accept':'application/json', ...(body === undefined ? {} : {'Content-Type':'application/json'})},
        ...(body === undefined ? {} : {body:JSON.stringify(body)})
      });
    } catch (_) { throw Error('NETWORK_OR_BROWSER_POLICY'); }
    if (!res.ok) throw Error('HTTP_' + res.status);
    try { return await res.json(); } catch (_) { throw Error('INVALID_JSON'); }
  }

  function data(v) { return v?.data ?? v; }
  function signedValue(name) { return signed?.get(name) || ''; }
  function sessionActive(v) {
    const x = data(v);
    return typeof x?.user?.id === 'string' && x.user.id.length > 0 &&
      !!x.session && typeof x.session === 'object';
  }
  async function checkSession(withVerifier) {
    const path = withVerifier
      ? '/get-session?neon_auth_session_verifier=' + encodeURIComponent(withVerifier)
      : '/get-session';
    return sessionActive(await api(path));
  }
  async function queryHash(query) {
    const bytes = new TextEncoder().encode(query);
    const digest = await crypto.subtle.digest('SHA-256', bytes);
    return Array.from(new Uint8Array(digest), b => b.toString(16).padStart(2,'0')).join('');
  }
  function clearPending() { try { sessionStorage.removeItem(pendingKey); } catch (_) {} }
  async function callbackWasStartedHere() {
    let marker;
    try { marker = JSON.parse(sessionStorage.getItem(pendingKey) || 'null'); }
    catch (_) { return false; }
    clearPending();
    return !!(marker && Number.isFinite(marker.at) && marker.at > 0 &&
      Date.now() >= marker.at && Date.now() - marker.at <= maxAgeMs &&
      marker.hash === await queryHash(signed.toString()));
  }

  async function verifySignedClient() {
    if (!signed) throw Error('INVALID_SIGNED_REQUEST');
    if (signedValue('scope') !== 'openid') throw Error('UNSUPPORTED_SCOPE');
    if (signedValue('resource') !== resource) throw Error('RESOURCE_MISMATCH');
    if (signedValue('response_type') !== 'code' || signedValue('code_challenge_method') !== 'S256')
      throw Error('UNSUPPORTED_OAUTH_FLOW');
    if (!signedValue('redirect_uri') || !usableRedirect(signedValue('redirect_uri')))
      throw Error('UNSAFE_CLIENT_REDIRECT');
    // Managed Neon verifies the signed oauth_query. The page NEVER trusts URL
    // client_id, client_name, scope, or resource prior to this response.
    const result = data(await api('/oauth2/public-client-prelogin', {
      method:'POST', body:{client_id:signedValue('client_id'), oauth_query:signed.toString()}
    }));
    const client = result?.client ?? result;
    const clientId = client?.client_id ?? client?.clientId;
    if (!client || clientId !== signedValue('client_id') || client?.disabled === true)
      throw Error('CLIENT_NOT_VERIFIED');
    return client;
  }

  async function followProviderReply(result) {
    const payload = data(result);
    if (payload?.redirect !== true) throw Error('NO_VERIFIED_REDIRECT');
    const dest = usableRedirect(payload.url);
    if (!dest) throw Error('UNSAFE_PROVIDER_REDIRECT');
    // Redirect comes only from the trusted, explicitly configured Neon origin.
    location.assign(dest);
  }
  function failure(e) {
    disableAll();
    const code = String(e?.message || 'ERROR');
    const safe = /^(HTTP_[0-9]{3}|NETWORK_OR_BROWSER_POLICY|INVALID_JSON|INVALID_SIGNED_REQUEST|UNSUPPORTED_SCOPE|RESOURCE_MISMATCH|UNSUPPORTED_OAUTH_FLOW|UNSAFE_CLIENT_REDIRECT|CLIENT_NOT_VERIFIED|NO_VERIFIED_REDIRECT|UNSAFE_PROVIDER_REDIRECT|CALLBACK_UNEXPECTED|CALLBACK_INVALID|BROWSER_STORAGE_UNAVAILABLE|NEON_SIGNIN_INVALID)$/.test(code) ? code : 'UNEXPECTED_ERROR';
    note('OAuth staging stopped [' + safe + ']. Return to ChatGPT and start a fresh request. No access was granted.');
  }
  function showConsent(client) {
    const name = typeof client.client_name === 'string' ? client.client_name :
      (typeof client.clientName === 'string' ? client.clientName : 'Registered OAuth client');
    const host = new URL(signedValue('redirect_uri')).hostname;
    document.getElementById('client-name').textContent = name.slice(0,160);
    document.getElementById('client-host').textContent = 'Return destination: ' + host + ' (client-chosen name, check carefully)';
    document.getElementById('scope').textContent = 'openid — verify your sign-in identity';
    document.getElementById('resource').textContent = 'Requested staging resource: ' + resource;
    document.getElementById('client').hidden = false;
    document.getElementById('rights').hidden = false;
    allow.disabled = false; deny.disabled = false;
    note('Review carefully. Approve and Deny both require your explicit click.');
  }
  async function initialize() {
    disableAll();
    try {
      if (!signed) throw Error('INVALID_SIGNED_REQUEST');
      const client = await verifySignedClient();
      if (mode === 'login') {
        if (hasVerifier) {
          if (!verifier || !/^[A-Za-z0-9_-]{12,2048}$/.test(verifier) || !(await callbackWasStartedHere()))
            throw Error('CALLBACK_UNEXPECTED');
        }
        const loggedIn = await checkSession(hasVerifier ? verifier : undefined);
        if (loggedIn) {
          note('Signed in with Neon. Resuming OAuth request…');
          return await followProviderReply(await api('/oauth2/continue', {
            method:'POST', body:{selected:true,oauth_query:signed.toString()}
          }));
        }
        if (hasVerifier) throw Error('CALLBACK_INVALID');
        signin.disabled = false;
        note('Neon verified the OAuth request. Continue with Google to sign in.');
      } else if (mode === 'consent') {
        if (!(await checkSession())) {
          const link = document.getElementById('login-link');
          link.href = '/auth/login?' + signed.toString();
          link.hidden = false;
          note('Sign in first. No OAuth consent was issued.');
          return;
        }
        showConsent(client);
      } else throw Error('INVALID_SIGNED_REQUEST');
    } catch (e) { failure(e); }
  }

  if (signin) signin.addEventListener('click', async () => {
    if (busy || !signed || signin.disabled) return;
    busy = true; disableAll(); note('Starting Google sign-in…');
    try {
      const callbackURL = location.origin + location.pathname + '?' + signed.toString();
      const response = data(await api('/sign-in/social', {method:'POST', body:{
        provider:'google', callbackURL, disableRedirect:true, oauth_query:signed.toString()
      }}));
      const dest = usableRedirect(response?.url, {neonOnly:true});
      if (!dest) throw Error('NEON_SIGNIN_INVALID');
      try { sessionStorage.setItem(pendingKey, JSON.stringify({at:Date.now(), hash:await queryHash(signed.toString())})); }
      catch (_) { throw Error('BROWSER_STORAGE_UNAVAILABLE'); }
      location.assign(dest);
    } catch (e) { clearPending(); failure(e); } finally { busy = false; }
  });
  async function decide(accept) {
    if (busy || !signed || allow.disabled) return;
    busy = true; disableAll(); note(accept ? 'Submitting approval to Neon…' : 'Submitting denial to Neon…');
    try {
      const result = await api('/oauth2/consent', {method:'POST', body:{
        accept, scope:accept ? 'openid' : undefined, oauth_query:signed.toString()
      }});
      await followProviderReply(result);
    } catch (e) { failure(e); } finally { busy = false; }
  }
  if (allow) allow.addEventListener('click', () => { void decide(true); });
  if (deny) deny.addEventListener('click', () => { void decide(false); });
  void initialize();
})();
'''


async def ui_js(request):
    if not configuration()["enabled"]:
        return Response(status_code=404)
    return Response(_JS, media_type="text/javascript", headers={
        "Cache-Control":"no-store, max-age=0", "X-Content-Type-Options":"nosniff",
        "Referrer-Policy":"no-referrer",
    })
