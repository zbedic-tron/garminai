"""GarminAI v0.9.0: managed Neon OAuth for exactly allowlisted staging clients.

No client-side signature verification is claimed. Neon verifies signed oauth_query
when consenting and validates authorize requests. Actual MCP/Garmin stays disabled.
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
    client_id = e.get("GARMINAI_OAUTH_TEST_CLIENT_ID", "").strip()
    issues = []
    if enabled and (not 8 <= len(client_id) <= 300 or not re.fullmatch(r"[A-Za-z0-9._~-]+", client_id)):
        issues.append("INVALID_STAGING_TEST_CLIENT_ID")
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
        "client_id": client_id if enabled and not issues else "",
        "callback": "https://" + hostname + "/auth/oauth-test/callback" if enabled and not issues else "",
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


def _response(*, mode: str, base: str, resource: str, client_id: str, callback: str) -> HTMLResponse:
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
    from .mcp_oauth_gateway import configured as mcp_demo_configured
    demo_tools = mcp_demo_configured()['enabled']
    notice = ('Staging only. This authorizes fictional, read-only MCP demo tools. '
              'It never connects Garmin accounts or real athlete data.' if demo_tools else
              'Staging only. This page never connects Garmin accounts or grants MCP tool access.')
    html = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(title)}</title><style>{_CSS}</style></head>
<body><main data-mode="{mode}" data-auth="{escape(base, quote=True)}" data-resource="{escape(resource, quote=True)}" data-client-id="{escape(client_id, quote=True)}" data-callback="{escape(callback, quote=True)}" data-chatgpt-client="{str(callback.startswith('https://chatgpt.com/')).lower()}" data-demo-tools="{str(demo_tools).lower()}">
<div class="brand">GARMINAI PUBLIC · OAUTH STAGING</div><h1>{escape(title)}</h1>
<p class="notice">{escape(notice)}</p>
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


def _profile_for_signed_request(request, c):
    """Select ONLY an operator-allowlisted client. The untrusted URL is used
    solely for *selection*, never for authorization or redirect construction.
    Neon validates the signed oauth_query before issuing code/consent.
    """
    from .chatgpt_staging import configuration as chatgpt_configuration
    selected = request.query_params.get('client_id') if hasattr(request, 'query_params') else None
    chatgpt = chatgpt_configuration()
    if chatgpt['enabled'] and selected == chatgpt['client_id']:
        return {**c, 'client_id':chatgpt['client_id'], 'callback':chatgpt['callback']}
    return c


async def login_page(request):
    c = configuration()
    if not c["enabled"]:
        return await disabled_login(request)
    c = _profile_for_signed_request(request, c)
    return _response(mode="login", base=c["neon_auth"], resource=c["resource"], client_id=c["client_id"], callback=c["callback"])


async def consent_page(request):
    c = configuration()
    if not c["enabled"]:
        return await disabled_consent(request)
    c = _profile_for_signed_request(request, c)
    return _response(mode="consent", base=c["neon_auth"], resource=c["resource"], client_id=c["client_id"], callback=c["callback"])


async def ui_status(request):
    c = configuration()
    from .mcp_oauth_gateway import configured as mcp_demo_configured
    demo_tools = mcp_demo_configured()['enabled']
    return JSONResponse({
        "version":"0.9.0", "mode":"STAGING_ONLY",
        "oauth_ui_staging_enabled": c["enabled"],
        "oauth_ui_config_errors": c["issues"] if c["requested"] else [],
        "provider_enabled_by_this_app": False,
        "mcp_authenticated_tools_enabled": False,
        "mcp_demo_oauth_tools_enabled": demo_tools,
        "garmin_live_data_enabled": False,
        "next":"Staging client and fictional MCP-only tools; Garmin access remains disabled.",
    }, headers={"Cache-Control":"no-store"})


_JS = r'''"use strict";
// GarminAI v0.9.0: operator-allowlisted staging client only; Neon validates
// the signed query when issuing code/consent. Browser cannot verify sig.
(() => {
  const root = document.querySelector('main[data-mode]');
  if (!root) return;
  const mode = root.dataset.mode;
  const base = root.dataset.auth;
  const resource = root.dataset.resource;
  const expectedClient = root.dataset.clientId;
  const expectedCallback = root.dataset.callback;
  const isChatGPT = root.dataset.chatgptClient === 'true';
  const demoTools = root.dataset.demoTools === 'true';
  const status = document.getElementById('status');
  const signin = document.getElementById('signin');
  const allow = document.getElementById('allow');
  const deny = document.getElementById('deny');
  const pendingKey = 'garminai.oauth-ui-staging.pending.v1';
  const resumeKey = 'garminai.oauth-ui-staging.resume.v0871';
  const maxAgeMs = 10 * 60 * 1000;
  let busy = false;
  const note = message => { status.textContent = message; };
  const disableAll = () => { for (const b of [signin, allow, deny]) if (b) b.disabled = true; };

  function signedRequest(params) {
    const names = params.getAll('ba_param');
    if (params.getAll('sig').length !== 1 || !params.get('sig') ||
        names.length < 1 || names.length > 48 || new Set(names).size !== names.length ||
        names.some(n => !/^[a-zA-Z][a-zA-Z0-9_]{0,63}$/.test(n)) ||
        params.toString().length > 8192) return null;
    const keys = new Set(['sig', 'ba_param', ...names]);
    const query = new URLSearchParams([...params].filter(([key]) => keys.has(key)));
    // Neon includes 'ba_param' in the signed name list itself. Its repeated
    // values enumerate signed fields; it is not a single-valued OAuth field.
    // All other declared signed parameters must appear exactly once.
    for (const name of names) {
      if (name !== 'ba_param' && query.getAll(name).length !== 1) return null;
    }
    if (!names.includes('client_id')) return null;
    return query;
  }

  const params = new URLSearchParams(location.search);
  const verifier = params.get('neon_auth_session_verifier');
  const hasVerifier = params.has('neon_auth_session_verifier');
  const signed = signedRequest(params);
  // Remove the one-time verifier before any fetch, DOM update or navigation.
  if (signed) history.replaceState(null, '', location.pathname + '?' + signed.toString());
  else if (location.search) history.replaceState(null, '', location.pathname);

  function usableRedirect(value, {neonOnly = false, providerReply = false} = {}) {
    if (typeof value !== 'string' || value.length > 4096) return null;
    let u;
    try { u = new URL(value); } catch (_) { return null; }
    if (u.protocol !== 'https:' || u.username || u.password || u.hash) return null;
    const auth = new URL(base);
    if (neonOnly) {
      if (u.origin !== auth.origin || u.pathname !== auth.pathname + '/sign-in/social/init' ||
          u.searchParams.size !== 1 || !/^[A-Za-z0-9_-]{16,256}$/.test(u.searchParams.get('token') || '')) return null;
    }
    if (providerReply) {
      const onNeon = u.origin === auth.origin && u.pathname.startsWith(auth.pathname + '/');
      const onOurApp = u.origin === location.origin &&
        ['/auth/login','/auth/consent','/auth/oauth-test/callback'].includes(u.pathname);
      // Only a configured exact ChatGPT callback may receive authorization
      // results. Reject any other external redirect or state mismatch.
      const configured = new URL(expectedCallback);
      const external = isChatGPT && u.origin === configured.origin &&
        u.pathname === configured.pathname &&
        u.searchParams.getAll('state').length === 1 &&
        u.searchParams.get('state') === signedValue('state') &&
        u.searchParams.has('code') !== u.searchParams.has('error') &&
        (!u.searchParams.has('iss') || u.searchParams.get('iss') === base) &&
        [...u.searchParams.keys()].every(k =>
          ['state','code','error','error_description','iss'].includes(k));
      if (!onNeon && !onOurApp && !external) return null;
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

  const data = v => v?.data ?? v;
  const signedValue = n => signed?.get(n) || '';
  const sessionActive = v => { const x = data(v); return !!(
    typeof x?.user?.id === 'string' && x.user.id && x.session && typeof x.session === 'object'); };
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
  const clearPending = () => { try {sessionStorage.removeItem(pendingKey);} catch (_) {} };
  async function callbackWasStartedHere() {
    let marker;
    try { marker = JSON.parse(sessionStorage.getItem(pendingKey) || 'null'); }
    catch (_) { return false; }
    clearPending();
    return !!(marker && Number.isFinite(marker.at) && marker.at > 0 &&
      Date.now() >= marker.at && Date.now() - marker.at <= maxAgeMs &&
      marker.hash === await queryHash(signed.toString()));
  }

  // Staging-only structural restrictions. These do NOT prove Neon's signature;
  // Neon will independently validate the client, redirect, scopes, PKCE, and
  // signed oauth_query when issuing any authorization code or accepting consent.
  function validateStagingRequest() {
    if (!signed) throw Error('INVALID_SIGNED_REQUEST');
    if (signedValue('client_id') !== expectedClient) throw Error('UNEXPECTED_CLIENT');
    if (signedValue('redirect_uri') !== expectedCallback) throw Error('UNSAFE_CLIENT_REDIRECT');
    if (isChatGPT) {
      // OpenID-only demo: allow only identity-related OIDC scopes, never Garmin
      // or write permissions. OpenAI can request additional default OIDC scopes.
      const scopes = signedValue('scope').split(' ').filter(Boolean);
      if (!scopes.includes('openid') || scopes.length > 3 ||
          new Set(scopes).size !== scopes.length ||
          scopes.some(s => !['openid','email','profile'].includes(s)))
        throw Error('UNSUPPORTED_SCOPE');
    } else if (signedValue('scope') !== 'openid') throw Error('UNSUPPORTED_SCOPE');
    if (signedValue('resource') !== resource) throw Error('RESOURCE_MISMATCH');
    const state = signedValue('state');
    if (signedValue('response_type') !== 'code' || signedValue('code_challenge_method') !== 'S256' ||
        !/^[A-Za-z0-9_-]{43}$/.test(signedValue('code_challenge')) ||
        (isChatGPT ? !/^[A-Za-z0-9._~-]{16,512}$/.test(state) : !/^[A-Za-z0-9_-]{43}$/.test(state)))
      throw Error('UNSUPPORTED_OAUTH_FLOW');
    const prompt = signedValue('prompt');
    if (isChatGPT ? (prompt && prompt !== 'consent') : prompt !== 'consent')
      throw Error('UNEXPECTED_PROMPT');
  }

  async function registeredClient() {
    const result = data(await api('/oauth2/public-client?client_id=' + encodeURIComponent(expectedClient)));
    const client = result?.client ?? result;
    const id = client?.client_id ?? client?.clientId;
    if (id !== expectedClient || client?.disabled === true) throw Error('CLIENT_NOT_VERIFIED');
    // public-client is display metadata. Neon can return redirect_uris: []
    // despite an actual registration (confirmed in Neon Console).
    // Preserve rejection of malformed or explicitly mismatching nonempty lists;
    // Neon remains authoritative for the signed request and redirect URI.
    const uris = client.redirect_uris ?? client.redirectUris;
    if (uris !== undefined &&
        (!Array.isArray(uris) || (uris.length > 0 && !uris.includes(expectedCallback))))
      throw Error('CLIENT_NOT_VERIFIED');
    return client;
  }

  async function resumeAtNeon() {
    validateStagingRequest();
    // Do not re-start /oauth2/authorize here. On the Render top-level site,
    // the fetch-visible Neon session can be partitioned from the first-party
    // session seen after navigating directly to Neon. A fresh authorize would
    // redirect to login again. Neon documents oauth2.continue({selected:true})
    // for login pages, even after the social sign-in callback.
    // Fail closed if the same signed state is repeatedly resumed.
    try {
      const last = JSON.parse(sessionStorage.getItem(resumeKey) || 'null');
      if (last?.state === signedValue('state') && Number.isFinite(last.at) &&
          Date.now() >= last.at && Date.now() - last.at < maxAgeMs)
        throw Error('OAUTH_SESSION_LOOP');
      sessionStorage.setItem(resumeKey, JSON.stringify({state:signedValue('state'),at:Date.now()}));
    } catch (e) {
      if (e?.message === 'OAUTH_SESSION_LOOP') throw e;
      throw Error('BROWSER_STORAGE_UNAVAILABLE');
    }
    note('Session established; asking Neon to continue the signed OAuth request…');
    // Selected:true is the Neon documented login-page continuation flag, NOT
    // a grant of access. Neon checks the signature/session and determines the
    // next step (usually Consent); our page cannot issue an OAuth code.
    const result = await api('/oauth2/continue', {method:'POST', body:{
      selected:true, oauth_query:signed.toString()
    }});
    await followProviderReply(result);
  }

  async function followProviderReply(result) {
    const payload = data(result);
    if (payload?.redirect !== true) throw Error('NO_VERIFIED_REDIRECT');
    const dest = usableRedirect(payload.url, {providerReply:true});
    if (!dest) throw Error('UNSAFE_PROVIDER_REDIRECT');
    location.assign(dest);
  }
  function failure(e) {
    disableAll();
    const code = String(e?.message || 'ERROR');
    const safe = /^(HTTP_[0-9]{3}|NETWORK_OR_BROWSER_POLICY|INVALID_JSON|INVALID_SIGNED_REQUEST|UNEXPECTED_CLIENT|UNEXPECTED_PROMPT|UNSUPPORTED_SCOPE|RESOURCE_MISMATCH|UNSUPPORTED_OAUTH_FLOW|UNSAFE_CLIENT_REDIRECT|CLIENT_NOT_VERIFIED|NO_VERIFIED_REDIRECT|UNSAFE_PROVIDER_REDIRECT|CALLBACK_UNEXPECTED|CALLBACK_INVALID|BROWSER_STORAGE_UNAVAILABLE|NEON_SIGNIN_INVALID|OAUTH_SESSION_LOOP)$/.test(code) ? code : 'UNEXPECTED_ERROR';
    note('OAuth staging stopped [' + safe + ']. Start a fresh OAuth test. No access was granted.');
  }
  function showConsent(client) {
    const name = typeof client.client_name === 'string' ? client.client_name :
      (typeof client.clientName === 'string' ? client.clientName : 'Registered OAuth test client');
    const host = new URL(expectedCallback).hostname;
    document.getElementById('client-name').textContent = name.slice(0,160);
    document.getElementById('client-host').textContent = 'Return destination: ' + host + ' (check carefully)';
    document.getElementById('scope').textContent = (isChatGPT ? signedValue('scope') : 'openid') + (demoTools ? ' — fictional read-only demo MCP tools only' : ' — verify your sign-in identity');
    document.getElementById('resource').textContent = 'Requested staging resource: ' + resource;
    document.getElementById('client').hidden = false;
    document.getElementById('rights').hidden = false;
    allow.disabled = false; deny.disabled = false;
    note('Registered staging client. Neon validates the signed request when you submit consent.');
  }
  async function initialize() {
    disableAll();
    try {
      validateStagingRequest();
      if (mode === 'login') {
        if (hasVerifier) {
          if (!verifier || !/^[A-Za-z0-9_-]{12,2048}$/.test(verifier) || !(await callbackWasStartedHere()))
            throw Error('CALLBACK_UNEXPECTED');
        }
        const loggedIn = await checkSession(hasVerifier ? verifier : undefined);
        if (loggedIn) return await resumeAtNeon();
        if (hasVerifier) throw Error('CALLBACK_INVALID');
        signin.disabled = false;
        note('Google sign-in available. Neon validates the authorization request; no access is granted on this page.');
      } else if (mode === 'consent') {
        if (!(await checkSession())) {
          const link = document.getElementById('login-link');
          link.href = '/auth/login?' + signed.toString();
          link.hidden = false;
          note('Sign in first. No OAuth consent was issued.');
          return;
        }
        // Only an authenticated Neon session can look up the registered client.
        showConsent(await registeredClient());
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
      try {sessionStorage.setItem(pendingKey, JSON.stringify({at:Date.now(),hash:await queryHash(signed.toString())}));}
      catch (_) {throw Error('BROWSER_STORAGE_UNAVAILABLE');}
      location.assign(dest);
    } catch (e) {clearPending();failure(e);} finally {busy=false;}
  });

  async function decide(accept) {
    if (busy || !signed || allow.disabled) return;
    busy = true; disableAll(); note(accept ? 'Submitting approval to Neon…' : 'Submitting denial to Neon…');
    try {
      const result = await api('/oauth2/consent', {method:'POST', body:{
        accept, ...(accept ? {scope:isChatGPT ? signedValue('scope') : 'openid'} : {}), oauth_query:signed.toString()
      }});
      await followProviderReply(result);
    } catch (e) {failure(e);} finally {busy=false;}
  }
  if (allow) allow.addEventListener('click', () => {void decide(true);});
  if (deny) deny.addEventListener('click', () => {void decide(false);});
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
