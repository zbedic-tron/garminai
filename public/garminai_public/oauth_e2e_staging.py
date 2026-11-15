"""v1.0.0 isolated, opt-in OAuth authorization-code+PKCE E2E smoke test.

NO real Garmin access, no MCP authorization, no token storage, no client secret.
Never return OAuth codes, provider tokens, user identifiers or raw errors.
The Neon auth-staging origin, MCP resource and OAuth test client are operator configured.
"""
import asyncio
import os
import re
import time
from collections import deque
from html import escape
from urllib.parse import urlsplit

import httpx
import jwt
from jwt.exceptions import PyJWTError
from starlette.responses import HTMLResponse, JSONResponse, Response

from .auth_staging_poc import validate_staging_auth_url
from .oauth_resource_staging import build_contract

_VERSION = '1.0.0'
_CLIENT = re.compile(r'^[A-Za-z0-9._~:/-]{8,512}$')
_CODE = re.compile(r'^[A-Za-z0-9._~+-]{12,2048}$')
_B64URL_43 = re.compile(r'^[A-Za-z0-9_-]{43}$')
_ALLOWED_ALGORITHMS = {'RS256': 'RSA', 'EdDSA': 'OKP', 'ES256': 'EC'}
_REQUEST_WINDOW = deque()
_MAX_EXCHANGES_PER_MINUTE = 15  # Process-local safety limit on shared free service.
_WINDOW_LOCK = asyncio.Lock()


def configuration(env=None):
    env = os.environ if env is None else env
    enabled = env.get('GARMINAI_OAUTH_E2E_STAGING_ENABLED') == '1'
    contract = build_contract(env)
    base = env.get('NEON_AUTH_STAGING_URL', '').strip()
    client = env.get('GARMINAI_OAUTH_TEST_CLIENT_ID', '').strip()
    errors = []
    if not validate_staging_auth_url(base) or base != contract.issuer:
        errors.append('NEON_ISSUER_MISMATCH')
    if not contract.complete:
        errors.append('MCP_OAUTH_STAGING_NOT_READY')
    if not _CLIENT.fullmatch(client) or not client.isascii() or client.startswith('http:'):
        errors.append('INVALID_TEST_CLIENT_ID')
    hostname = contract.hostname
    if hostname != 'garminai-public-demo.onrender.com':
        # Intentional fixed host guard for this public demonstration.
        errors.append('UNEXPECTED_TEST_HOST')
    return {
        'enabled': enabled and not errors,
        'requested': enabled,
        'issues': errors,
        'issuer': base,
        'client_id': client,
        'resource': contract.resource,
        'origin': 'https://' + hostname if not errors else '',
        'callback': 'https://' + hostname + '/auth/oauth-test/callback' if not errors else '',
    }


def _headers(csp=None):
    headers = {
        'Cache-Control': 'no-store, max-age=0', 'Pragma': 'no-cache',
        'Referrer-Policy': 'no-referrer', 'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'DENY', 'Permissions-Policy': 'camera=(), microphone=(), geolocation=()',
    }
    if csp: headers['Content-Security-Policy'] = csp
    return headers


async def status(_request):
    c = configuration()
    from .mcp_oauth_gateway import configured as mcp_demo_configured
    return JSONResponse({
        'version': _VERSION, 'mode': 'STAGING_ONLY',
        'oauth_e2e_test_enabled': c['enabled'],
        'configuration_issues': c['issues'] if c['requested'] else [],
        'test_callback_url': c['callback'] if c['enabled'] else None,
        'token_exchange': 'SERVER_SIDE_NO_TOKEN_STORAGE',
        'mcp_authenticated_tools_enabled': False, 'garmin_live_data_enabled': False,
        'mcp_demo_oauth_tools_enabled': mcp_demo_configured()['enabled'],
    }, headers=_headers())


_PAGE = '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>GarminAI OAuth E2E test</title>
<style>:root{font:16px system-ui,sans-serif;color-scheme:dark}*{box-sizing:border-box}body{background:#0b1220;color:#ecf4fa;display:grid;place-items:center;min-height:100vh;margin:0;padding:18px}main{max-width:620px;width:100%;padding:30px;border:1px solid #41516b;border-radius:16px;background:#172538}.brand{color:#76ead4;font-weight:750}p{line-height:1.5}button{background:#157763;border:1px solid #a6f4df;color:white;border-radius:8px;padding:12px 16px;min-height:44px;cursor:pointer}button:disabled{opacity:.5;cursor:not-allowed}#status{white-space:pre-wrap}small{color:#b8c9d8}</style></head><body>
<main data-oauth-test="1" data-mode="{mode}" data-issuer="{issuer}" data-client-id="{client}" data-resource="{resource}" data-callback="{callback}">
<p class="brand">GARMINAI PUBLIC · OAUTH TEST STAGING</p><h1>Authorization code + PKCE/S256</h1>
<p>Independent OAuth diagnostic. When the separate demo switch is enabled, it also checks fictional, read-only MCP tools. Never real Garmin data.</p>
{button}
<p id="status" role="status" aria-live="polite">{initial}</p>
<small>Client: public (no secret). Scope: openid only. Your token is checked transiently by the server and never displayed or stored.</small>
</main><script src="/auth/oauth-test.js" defer></script></body></html>'''


def _page(mode):
    c = configuration()
    if not c['enabled']:
        return Response(status_code=404, headers=_headers())
    button = '<button type="button" id="start">Start OAuth test</button>' if mode == 'start' else ''
    initial = 'Ready to begin a fresh staging OAuth request.' if mode == 'start' else 'Checking callback securely…'
    html = _PAGE
    for token, value in {
        '{mode}':mode, '{issuer}':escape(c['issuer'], quote=True),
        '{client}':escape(c['client_id'], quote=True),
        '{resource}':escape(c['resource'], quote=True),
        '{callback}':escape(c['callback'], quote=True),
        '{button}':button, '{initial}':initial,
    }.items():
        html = html.replace(token, value)
    csp = ("default-src 'none'; base-uri 'none'; object-src 'none'; frame-ancestors 'none'; "
           "script-src 'self'; style-src 'unsafe-inline'; connect-src 'self'; form-action 'none'")
    return HTMLResponse(html, headers=_headers(csp))


async def start(_request): return _page('start')
async def callback(_request): return _page('callback')


async def script(_request):
    if not configuration()['enabled']: return Response(status_code=404)
    return Response(_JS, media_type='text/javascript', headers=_headers())


class UnsafeOAuthResponse(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _check_jwt(access_token, keys, *, issuer, resource, client_id, return_claims=False):
    # This smoke test requires a resource-bound JWT; opaque tokens are fail-closed.
    if not isinstance(access_token, str) or not 64 <= len(access_token) <= 8192:
        raise UnsafeOAuthResponse('ACCESS_TOKEN_NOT_JWT')
    if not isinstance(keys, dict) or not isinstance(keys.get('keys'), list):
        raise UnsafeOAuthResponse('JWKS_INVALID')
    try:
        header = jwt.get_unverified_header(access_token)
    except (PyJWTError, ValueError, TypeError) as exc:
        raise UnsafeOAuthResponse('ACCESS_TOKEN_NOT_JWT') from exc
    algorithm, kid = header.get('alg'), header.get('kid')
    if algorithm not in _ALLOWED_ALGORITHMS or not isinstance(kid, str) or not 1 <= len(kid) <= 128:
        raise UnsafeOAuthResponse('JWT_ALGORITHM_INVALID')
    if header.get('typ', '').lower() != 'at+jwt':
        raise UnsafeOAuthResponse('JWT_TYPE_INVALID')
    if any(key in header for key in ('jku', 'x5u', 'jwk')):
        raise UnsafeOAuthResponse('JWT_HEADER_INVALID')
    matches = [j for j in keys['keys'] if isinstance(j, dict) and j.get('kid') == kid]
    if len(matches) != 1 or matches[0].get('kty') != _ALLOWED_ALGORITHMS[algorithm]:
        raise UnsafeOAuthResponse('JWT_KID_INVALID')
    jwk = matches[0]
    if jwk.get('alg', algorithm) != algorithm or jwk.get('use', 'sig') != 'sig':
        raise UnsafeOAuthResponse('JWT_KEY_INVALID')
    try:
        signing_key = jwt.PyJWK.from_dict(jwk, algorithm=algorithm).key
        claims = jwt.decode(
            access_token, signing_key, algorithms=[algorithm], issuer=issuer,
            audience=resource, leeway=30,
            options={'require': ['iss', 'sub', 'aud', 'exp', 'iat', 'scope', 'azp'], 'verify_nbf': True},
        )
    except (PyJWTError, TypeError, ValueError) as exc:
        raise UnsafeOAuthResponse('JWT_VALIDATION_FAILED') from exc
    # Access tokens are credentials for every MCP request. Fail closed as soon
    # as `exp` is reached: PyJWT's small clock-skew leeway is useful for some
    # claims but MUST NOT extend the access token's lifetime at this resource.
    # Refresh is handled by the OAuth client and Neon, never by this server.
    expiry = claims.get('exp')
    if type(expiry) not in (int, float) or expiry <= time.time():
        raise UnsafeOAuthResponse('JWT_EXPIRED')
    scope = claims.get('scope')
    granted = set(scope.split()) if isinstance(scope, str) else set(scope) if isinstance(scope, list) and all(isinstance(s, str) for s in scope) else set()
    if 'openid' not in granted or claims.get('azp') != client_id or not isinstance(claims.get('sub'), str) or not claims['sub']:
        raise UnsafeOAuthResponse('JWT_CLAIMS_INVALID')
    return claims if return_claims else True


def _rpc_payload(response, expected_id):
    """Parse an MCP JSON-mode response, reject errors and ambiguous shapes."""
    if response.status_code != 200 or len(response.content) > 64 * 1024:
        raise ValueError('MCP_HTTP_OR_SIZE')
    data = response.json()
    if (not isinstance(data, dict) or data.get('jsonrpc') != '2.0'
            or data.get('id') != expected_id or 'error' in data):
        raise ValueError('MCP_RPC_INVALID')
    result = data.get('result')
    if not isinstance(result, dict) or result.get('isError') is True:
        raise ValueError('MCP_TOOL_ERROR')
    return result


def _tool_output(result):
    """Only JSON object tool output is accepted, no raw response echo."""
    if isinstance(result.get('structuredContent'), dict):
        return result['structuredContent']
    blocks = result.get('content')
    if not isinstance(blocks, list) or len(blocks) != 1:
        raise ValueError('MCP_TOOL_CONTENT')
    block = blocks[0]
    if not isinstance(block, dict) or block.get('type') != 'text':
        raise ValueError('MCP_TOOL_CONTENT')
    obj = __import__('json').loads(block.get('text', ''))
    if not isinstance(obj, dict):
        raise ValueError('MCP_TOOL_CONTENT')
    return obj


async def _probe_demo_mcp(access_token, c):
    """Real in-process MCP JSON-RPC roundtrip for tools/list and three tools.

    Returns only boolean check flags; neither token, subject nor activities are
    ever returned to the test browser. Any failure is a PARTIAL PASS, not proof.
    """
    checks = {'tools_list':False,'get_sync_status':False,'get_activities':False,
              'get_demo_activity_details':False,'cross_owner_denied':False}
    try:
        from .http_server import app
        transport = httpx.ASGITransport(app=app)
        headers = {'Authorization': 'Bearer ' + access_token,
                   'Accept': 'application/json, text/event-stream',
                   'Content-Type': 'application/json',
                   'MCP-Protocol-Version': '2025-03-26'}
        async with httpx.AsyncClient(transport=transport, base_url=c['origin'],
                                     timeout=8.0, follow_redirects=False) as cli:
            async def rpc(number, method, params):
                r = await cli.post('/mcp-oauth-staging', headers=headers,
                    json={'jsonrpc':'2.0', 'id':number, 'method':method, 'params':params})
                return _rpc_payload(r, number)
            _rpc_payload(await cli.post('/mcp-oauth-staging', headers=headers,
                json={'jsonrpc':'2.0','id':1,'method':'initialize',
                      'params':{'protocolVersion':'2025-03-26','capabilities':{},
                                'clientInfo':{'name':'GarminAI staging E2E diagnostic',
                                              'version':'1.0.0'}}}), 1)
            listing = await rpc(2,'tools/list',{})
            names = {item.get('name') for item in listing.get('tools', [])
                     if isinstance(item, dict)}
            if names != {'get_sync_status','get_activities','get_demo_activity_details'}:
                return checks
            checks['tools_list'] = True
            sync = _tool_output(await rpc(3,'tools/call',
                               {'name':'get_sync_status','arguments':{}}))
            if sync.get('mode') != 'DEMO_ONLY' or sync.get('garmin_oauth') != 'NOT_CONNECTED':
                return checks
            checks['get_sync_status'] = True
            activities = _tool_output(await rpc(4,'tools/call',
                                {'name':'get_activities','arguments':{'limit':2}}))
            rows = activities.get('activities')
            if (activities.get('mode') != 'DEMO_ONLY' or
                    activities.get('isolation') != 'TOKEN_SUBJECT_SCOPED' or
                    not isinstance(rows, list) or len(rows) != 2 or
                    any(not isinstance(row,dict) or not isinstance(row.get('id'),str)
                        for row in rows)):
                return checks
            checks['get_activities'] = True
            owned_id = rows[0]['id']
            detail = _tool_output(await rpc(5,'tools/call',
                      {'name':'get_demo_activity_details','arguments':{'activity_id':owned_id}}))
            if (detail.get('mode') != 'DEMO_ONLY' or
                not isinstance(detail.get('activity'),dict) or
                detail['activity'].get('id') != owned_id):
                return checks
            checks['get_demo_activity_details'] = True
            # Forged/foreign IDs are forbidden. The actual two-user isolation
            # test with two distinct signed subjects runs offline in unit tests.
            other = _tool_output(await rpc(6,'tools/call',
                      {'name':'get_demo_activity_details',
                       'arguments':{'activity_id':'demo-0000000000000000-demo-run-001'}}))
            checks['cross_owner_denied'] = (other ==
                {'mode':'DEMO_ONLY','error':'unknown_demo_activity'})
    except (httpx.HTTPError, ValueError, TypeError, RuntimeError, ImportError, KeyError):
        return checks
    return checks


async def _exchange_and_verify(code, verifier, c):
    base = c['issuer']
    redirect_uri = c['callback']
    data = {
        'grant_type': 'authorization_code', 'client_id': c['client_id'],
        'code': code, 'redirect_uri': redirect_uri,
        'code_verifier': verifier, 'resource': c['resource'],
    }
    timeout = httpx.Timeout(8.0, connect=4.0)
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False, trust_env=False) as client:
            token_resp = await client.post(base + '/oauth2/token', data=data,
                    headers={'Accept':'application/json', 'Cache-Control':'no-store'})
            if token_resp.status_code != 200:
                raise UnsafeOAuthResponse('TOKEN_EXCHANGE_REJECTED_' + str(token_resp.status_code))
            if len(token_resp.content) > 32768:
                raise UnsafeOAuthResponse('TOKEN_RESPONSE_TOO_LARGE')
            try: tokens = token_resp.json()
            except ValueError as exc: raise UnsafeOAuthResponse('TOKEN_RESPONSE_INVALID') from exc
            if not isinstance(tokens, dict) or tokens.get('token_type','').lower() != 'bearer':
                raise UnsafeOAuthResponse('TOKEN_RESPONSE_INVALID')
            access_token = tokens.get('access_token')
            jwks_resp = await client.get(base + '/.well-known/jwks.json',
                              headers={'Accept':'application/json'})
            if jwks_resp.status_code != 200 or len(jwks_resp.content) > 65536:
                raise UnsafeOAuthResponse('JWKS_UNAVAILABLE')
            try: jwks = jwks_resp.json()
            except ValueError as exc: raise UnsafeOAuthResponse('JWKS_INVALID') from exc
    except httpx.HTTPError as exc:
        raise UnsafeOAuthResponse('NEON_NETWORK_FAILURE') from exc
    _check_jwt(access_token, jwks, issuer=base, resource=c['resource'], client_id=c['client_id'])
    # Optional demo-only MCP check uses the same ephemeral access token. No
    # bearer or verified subject is returned to the browser or persisted.
    from .mcp_oauth_gateway import configured as mcp_demo_configured
    probe = 'NOT_ENABLED'
    checks = {}
    if mcp_demo_configured()['enabled']:
        try:
            checks = await asyncio.wait_for(_probe_demo_mcp(access_token, c), timeout=20)
            probe = 'PASS' if checks and all(checks.values()) else 'FAILED'
        except Exception:
            # Staging MCP failures never leak token nor mask verified PKCE.
            probe = 'FAILED'
    return {'result':'OAUTH_STAGING_VERIFIED', 'authorization_code_exchanged': True,
            'jwt_signature_issuer_audience_scope_client_verified': True,
            'mcp_demo_probe': probe, 'mcp_demo_checks': checks,
            'mcp_authorized': False, 'garmin_access': False}


async def exchange(request):
    c = configuration()
    if not c['enabled']:
        return JSONResponse({'error':'STAGING_DISABLED'}, status_code=404, headers=_headers())
    # No CORS; allow only XMLHttpRequest/fetch from this origin and its page.
    if (request.headers.get('origin') != c['origin'] or
        request.headers.get('sec-fetch-site', 'same-origin') != 'same-origin'):
        return JSONResponse({'error':'ORIGIN_REJECTED'}, status_code=403, headers=_headers())
    if request.headers.get('content-type', '').split(';')[0].strip().lower() != 'application/json':
        return JSONResponse({'error':'UNSUPPORTED_CONTENT_TYPE'}, status_code=415, headers=_headers())
    try: size_hint = int(request.headers.get('content-length', '0') or '0')
    except ValueError: size_hint = 4097
    if size_hint < 0 or size_hint > 4096:
        return JSONResponse({'error':'REQUEST_TOO_LARGE'}, status_code=413, headers=_headers())
    body_bytes = await request.body()
    if len(body_bytes) > 4096:
        return JSONResponse({'error':'REQUEST_TOO_LARGE'}, status_code=413, headers=_headers())
    try:
        import json
        body = json.loads(body_bytes)
        if not isinstance(body, dict) or set(body) != {'code', 'code_verifier'}:
            raise ValueError('invalid body')
        code, verifier = body['code'], body['code_verifier']
        if not isinstance(code, str) or not _CODE.fullmatch(code) or not isinstance(verifier, str) or not _B64URL_43.fullmatch(verifier):
            raise ValueError('invalid values')
    except (ValueError, TypeError):
        return JSONResponse({'error':'INVALID_REQUEST'}, status_code=400, headers=_headers())
    # Process-wide cap avoids accidental amplification against Neon on the free plan.
    async with _WINDOW_LOCK:
        now = time.monotonic()
        while _REQUEST_WINDOW and _REQUEST_WINDOW[0] < now - 60: _REQUEST_WINDOW.popleft()
        if len(_REQUEST_WINDOW) >= _MAX_EXCHANGES_PER_MINUTE:
            return JSONResponse({'error':'RATE_LIMITED'}, status_code=429, headers=_headers())
        _REQUEST_WINDOW.append(now)
    try:
        result = await _exchange_and_verify(code, verifier, c)
        return JSONResponse(result, headers=_headers())
    except UnsafeOAuthResponse as exc:
        return JSONResponse({'result':'STAGING_VERIFICATION_FAILED','error':exc.code,
                             'mcp_authorized':False,'garmin_access':False},
                            status_code=400, headers=_headers())


_JS = r'''"use strict";
// GarminAI v1.0.0 public-client OAuth diagnostic, no token or code display/storage.
(() => {
  const root = document.querySelector('main[data-oauth-test]');
  if (!root) return;
  const mode = root.dataset.mode;
  const issuer = root.dataset.issuer;
  const clientId = root.dataset.clientId;
  const resource = root.dataset.resource;
  const callback = root.dataset.callback;
  const note = s => {document.getElementById('status').textContent=s;};
  const storageKey = 'garminai.oauth-test.v087';
  const maxAge = 10 * 60 * 1000;
  const b64url = bytes => btoa(String.fromCharCode(...bytes)).replace(/\+/g,'-').replace(/\//g,'_').replace(/=+$/,'');
  const fresh = () => b64url(crypto.getRandomValues(new Uint8Array(32)));
  const valid = (s) => typeof s === 'string' && /^[A-Za-z0-9_-]{43}$/.test(s);
  const params = new URLSearchParams(location.search);
  // Clear any incoming code/state/issuer BEFORE making any request or updating DOM.
  if (location.search) history.replaceState(null, '', location.pathname);
  const clear = () => {try {sessionStorage.removeItem(storageKey);}catch (_) {}};
  function pending() {
    try {return JSON.parse(sessionStorage.getItem(storageKey) || 'null');}
    catch (_) {return null;}
  }
  function correctMarker(m) {
    return !!(m && valid(m.verifier) && valid(m.state) && Number.isFinite(m.at) &&
      Date.now() >= m.at && Date.now()-m.at <= maxAge &&
      m.issuer === issuer && m.clientId === clientId &&
      m.resource === resource && m.callback === callback);
  }
  const start = document.getElementById('start');
  if (mode === 'start' && start) {
    start.addEventListener('click', async () => {
      start.disabled=true;
      clear(); note('Creating a new PKCE/S256 request…');
      try {
        const verifier = fresh(); const state = fresh();
        const hash = await crypto.subtle.digest('SHA-256',new TextEncoder().encode(verifier));
        const challenge = b64url(new Uint8Array(hash));
        sessionStorage.setItem(storageKey,JSON.stringify({verifier,state,at:Date.now(),
                                  issuer,clientId,resource,callback}));
        const url = new URL(issuer + '/oauth2/authorize');
        const query = {
          response_type:'code', client_id:clientId,redirect_uri:callback,
          scope:'openid', resource, state,code_challenge:challenge,
          code_challenge_method:'S256',prompt:'consent'
        };
        for (const [k,v] of Object.entries(query)) url.searchParams.set(k,v);
        location.assign(url.href);
      } catch (_) {clear();note('Browser could not start PKCE. No OAuth request was sent.');start.disabled=false;}
    });
    return;
  }
  if (mode !== 'callback') return;
  const marker = pending(); clear();
  if (!correctMarker(marker)) {note('Callback rejected: no matching fresh OAuth request in this browser tab.');return;}
  const receivedState = params.getAll('state');
  const receivedIssuer = params.getAll('iss');
  const errors = params.getAll('error');
  if (receivedState.length !== 1 || receivedState[0] !== marker.state ||
      receivedIssuer.length !== 1 || receivedIssuer[0] !== issuer) {
    note('Callback rejected: state or issuer mismatch. No code exchanged.');return;
  }
  if (errors.length === 1 && errors[0] === 'access_denied' && params.getAll('code').length === 0) {
    note('Consent denied by user. No token was requested.');return;
  }
  const codes=params.getAll('code');
  if (errors.length || codes.length !== 1 || !/^[A-Za-z0-9._~+-]{12,2048}$/.test(codes[0])) {
    note('OAuth returned an error or invalid code. No token requested.');return;
  }
  note('Code and issuer validated locally. Exchanging with Neon on the server…');
  void (async () => {
    try {
      const response=await fetch('/auth/oauth-test/exchange',{
        method:'POST',credentials:'same-origin',cache:'no-store',redirect:'error',
        headers:{'Content-Type':'application/json','Accept':'application/json'},
        body:JSON.stringify({code:codes[0],code_verifier:marker.verifier})
      });
      const result=await response.json();
      if (response.ok && result?.result === 'OAUTH_STAGING_VERIFIED' &&
          result?.mcp_authorized === false && result?.garmin_access === false) {
        if (result?.mcp_demo_probe === 'PASS')
          note('PASS: Neon OAuth + PKCE + verified JWT + MCP tools/list and tools/call (status, activities, owned details) + foreign-ID denial. Fictional data only; real MCP/Garmin access disabled.');
        else if (result?.mcp_demo_probe === 'FAILED')
          note('PARTIAL PASS: Neon OAuth verified; authenticated MCP demo probe failed. No live Garmin data or production MCP access.');
        else
          note('PASS: authorization code exchanged; Neon access token signature, issuer, audience, scope and client verified. Demo MCP tool probe not enabled; live Garmin access disabled.');
      }
      else note('Staging stopped [' + (/^[A-Z0-9_]{3,48}$/.test(result?.error||'') ? result.error : 'EXCHANGE_FAILED') + ']. No MCP/Garmin access.');
    } catch (_) {note('Staging stopped [NETWORK_OR_BROWSER_POLICY]. No MCP/Garmin access.');}
  })();
})();
'''
