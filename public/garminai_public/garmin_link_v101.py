"""v1.0.2 Garmin OAuth account-link staging, separated from all demo MCP data.

Operator opt-in, browser confirmation, short-lived authenticated encrypted ticket,
PKCE S256, browser-bound callback state, durable one-time replay lock and
Neon RLS. Never accepts a user identifier from browser, Garmin push, or tools.
Push and actual Garmin activity access stay disabled.
"""
import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import time
from urllib.parse import urlencode, parse_qs, urlsplit, urlunsplit, parse_qsl

import httpx
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse

from .garmin_oauth import (create_authorization_attempt, build_authorization_url,
                            exchange_code, refresh_access, garmin_user_id, garmin_permissions)
from .identity import VerifiedPrincipal, principal_from_verified_neon_claims, principal_from_sealed_link
from .postgres_store import validate_database_url
from .token_vault import TokenVault, load_key

CALLBACK = 'https://garminai-public-demo.onrender.com/garmin/oauth/callback'
BASE = 'https://garminai-public-demo.onrender.com'
COOKIE = '__Host-garminai_link'
OAUTH_COOKIE = '__Host-garminai_oauth'
SECRET_AAD = b'garminai:v101:ticket'
STATE_AAD = b'garminai:v101:oauth-state'
MAX_TICKET = 2048
_TICKET_CHARS = re.compile(r'^[A-Za-z0-9_-]{40,2048}$')
_CODE_CHARS = re.compile(r'^[A-Za-z0-9._~-]{8,2048}$')
_GARMIN_USER = re.compile(r'^[A-Za-z0-9._:-]{1,128}$')
_SAFE_HEADERS = {
    'Cache-Control':'no-store, max-age=0', 'Pragma':'no-cache',
    'Referrer-Policy':'no-referrer', 'X-Content-Type-Options':'nosniff',
    'X-Frame-Options':'DENY', 'Permissions-Policy':'camera=(), microphone=(), geolocation=()'
}
_HTML_HEADERS = dict(_SAFE_HEADERS, **{'Content-Security-Policy':
    "default-src 'none'; base-uri 'none'; object-src 'none'; frame-ancestors 'none'; "
    "style-src 'unsafe-inline'; form-action 'self'; script-src 'none'"})
# Chromium can apply form-action policy to the final location of a 303
# redirected POST form. Allow *only* Garmin's OAuth host for the browser
# confirmation page; the generic/error pages keep same-origin-only CSP.
_CONNECT_HEADERS = dict(_HTML_HEADERS, **{'Content-Security-Policy':
    "default-src 'none'; base-uri 'none'; object-src 'none'; frame-ancestors 'none'; "
    "style-src 'unsafe-inline'; form-action 'self' https://connect.garmin.com; script-src 'none'"})


def configuration(env=None):
    e = os.environ if env is None else env
    requested = e.get('GARMINAI_GARMIN_LINK_STAGING_ENABLED') == '1'
    errors = []
    if not re.fullmatch(r'[A-Za-z0-9._:-]{8,128}',e.get('GARMIN_CLIENT_ID','')): errors.append('GARMIN_CLIENT_ID_INVALID')
    secret=e.get('GARMIN_CLIENT_SECRET','')
    if not isinstance(secret,str) or not 12 <= len(secret) <= 1024 or any(ord(ch)<32 for ch in secret):
        errors.append('GARMIN_CLIENT_SECRET_INVALID')
    if e.get('GARMIN_REDIRECT_URI', '') != CALLBACK: errors.append('GARMIN_CALLBACK_MISMATCH')
    try: validate_database_url(e.get('DATABASE_URL', ''))
    except ValueError: errors.append('GARMIN_DATABASE_UNAVAILABLE')
    try: load_key(e.get('GARMINAI_TOKEN_ENCRYPTION_KEY', ''))
    except ValueError: errors.append('GARMIN_ENCRYPTION_KEY_INVALID')
    return {'requested':requested, 'enabled':requested and not errors,
            'issues':errors if requested else [], 'callback':CALLBACK,
            'push_enabled':False, 'real_mcp_enabled':False}


def _b64(raw): return base64.urlsafe_b64encode(raw).rstrip(b'=').decode('ascii')


def _unb64(token):
    if not isinstance(token,str) or not _TICKET_CHARS.fullmatch(token):
        raise ValueError('INVALID_OAUTH_STATE')
    decoded=base64.urlsafe_b64decode(token + '=' * (-len(token) % 4))
    if _b64(decoded) != token: raise ValueError('NONCANONICAL_OAUTH_STATE')
    return decoded


def _seal(payload, key, aad):
    plaintext = json.dumps(payload, separators=(',', ':'), sort_keys=True).encode('utf-8')
    if len(plaintext) > 1200: raise ValueError('OAUTH_STATE_TOO_LARGE')
    nonce=secrets.token_bytes(12)
    return _b64(nonce + AESGCM(key).encrypt(nonce, plaintext, aad))


def _open(token, key, aad, now=None):
    raw=_unb64(token)
    if not 30 <= len(raw) <= 2048: raise ValueError('INVALID_OAUTH_STATE')
    try:
        obj=json.loads(AESGCM(key).decrypt(raw[:12], raw[12:], aad))
    except (ValueError, TypeError, UnicodeError, InvalidTag) as exc:
        raise ValueError('INVALID_OAUTH_STATE') from exc
    n=int(time.time() if now is None else now)
    if (not isinstance(obj,dict) or type(obj.get('exp')) is not int
            or type(obj.get('iat')) is not int or obj['iat'] > n+5 or obj['exp'] <= n
            or obj['exp']-obj['iat'] > 600 or not isinstance(obj.get('subject'), str)
            or not re.fullmatch(r'[0-9a-f]{64}', obj['subject'])):
        raise ValueError('OAUTH_STATE_EXPIRED_OR_INVALID')
    return obj


def issue_ticket(principal, *, key, now=None):
    if not isinstance(principal,VerifiedPrincipal): raise PermissionError('NEON_LOGIN_REQUIRED')
    n=int(time.time() if now is None else now)
    return _seal({'subject':principal.subject,'iat':n,'exp':n+600,'version':1},key,SECRET_AAD)


def validate_ticket(ticket, *, key, now=None):
    payload=_open(ticket,key,SECRET_AAD,now)
    if payload.get('version') != 1: raise ValueError('INVALID_OAUTH_TICKET')
    return payload


def make_state(principal, verifier, cookie, *, key, now=None):
    if not isinstance(principal,VerifiedPrincipal): raise PermissionError('NEON_LOGIN_REQUIRED')
    if not isinstance(verifier,str) or not 43 <= len(verifier) <= 128:
        raise ValueError('INVALID_VERIFIER')
    if not isinstance(cookie,str) or not re.fullmatch('[A-Za-z0-9_-]{32,128}',cookie):
        raise ValueError('INVALID_BROWSER_COOKIE')
    n=int(time.time() if now is None else now)
    return _seal({'subject':principal.subject,'verifier':verifier,'browser':hashlib.sha256(cookie.encode()).hexdigest(),
                  'version':1,'iat':n,'exp':n+600},key,STATE_AAD)


def validate_state(state,cookie, *,key,now=None):
    payload=_open(state,key,STATE_AAD,now)
    if (payload.get('version') != 1 or not isinstance(payload.get('verifier'),str)
            or not 43 <= len(payload['verifier']) <= 128 or
            not isinstance(cookie,str) or
            not hmac.compare_digest(payload.get('browser',''),hashlib.sha256(cookie.encode()).hexdigest())):
        raise ValueError('BROWSER_OR_STATE_MISMATCH')
    return payload


def _db_cursor(principal):
    """Factory for short RLS transactions; intentionally imported lazily.

    Requires the existing least-privileged garminai_app database role.
    """
    from contextlib import contextmanager
    @contextmanager
    def enter():
        import psycopg
        with psycopg.connect(validate_database_url(os.environ.get('DATABASE_URL','')),connect_timeout=8) as conn:
            with conn.cursor() as cur:
                cur.execute('SELECT current_user')
                if cur.fetchone()[0] != 'garminai_app': raise PermissionError('UNSAFE_DATABASE_ROLE')
                cur.execute("SELECT set_config('garminai.subject', %s, true)",(principal.subject,))
                yield cur
    return enter()


def _consume_callback(principal, state):
    digest=hashlib.sha256(state.encode('ascii')).hexdigest()
    with _db_cursor(principal) as cur:
        cur.execute('''INSERT INTO garminai.garmin_oauth_used_states (subject,state_hash,expires_at)
                       VALUES (%s,%s,now() + interval '15 minutes') ON CONFLICT DO NOTHING
                       RETURNING state_hash''',(principal.subject,digest))
        if cur.fetchone() is None: raise PermissionError('REPLAYED_OAUTH_STATE')


def _store_link(principal, garmin_id, token, perms, key):
    if not _GARMIN_USER.fullmatch(garmin_id): raise ValueError('GARMIN_USER_ID_INVALID')
    if not isinstance(perms,list) or 'ACTIVITY_EXPORT' not in perms:
        raise PermissionError('ACTIVITY_EXPORT_NOT_GRANTED')
    if (not isinstance(token,dict) or
            any(not isinstance(token.get(k),str) or not token[k] for k in ('access_token','refresh_token'))):
        raise ValueError('TOKEN_RESPONSE_INVALID')
    expiry=token.get('expires_in')
    if type(expiry) is not int or not 60 <= expiry <= 7776000:
        raise ValueError('TOKEN_LIFETIME_INVALID')
    stored=json.dumps({'access_token':token['access_token'], 'refresh_token':token['refresh_token'],
        'expires_at':int(time.time())+expiry,'garmin_user_id':garmin_id, 'permissions':perms},
        separators=(',',':')).encode('utf-8')
    nonce,blob=TokenVault(key).seal(principal,stored)
    with _db_cursor(principal) as cur:
        cur.execute('INSERT INTO garminai.athletes (subject) VALUES (%s) ON CONFLICT DO NOTHING',(principal.subject,))
        cur.execute('SELECT garmin_user_id FROM garminai.athletes WHERE subject=%s FOR UPDATE',(principal.subject,))
        existing=cur.fetchone()
        if existing is None or (existing[0] is not None and existing[0] != garmin_id):
            raise PermissionError('DIFFERENT_GARMIN_ACCOUNT_ALREADY_LINKED')
        cur.execute('UPDATE garminai.athletes SET garmin_user_id=%s WHERE subject=%s',(garmin_id,principal.subject))
        cur.execute('''INSERT INTO garminai.garmin_credentials (subject,encrypted_blob,nonce)
                       VALUES (%s,%s,%s) ON CONFLICT(subject) DO UPDATE SET
                       encrypted_blob=EXCLUDED.encrypted_blob,nonce=EXCLUDED.nonce,updated_at=now()''',
                    (principal.subject,blob,nonce))


def _link_status(principal):
    with _db_cursor(principal) as cur:
        cur.execute('''SELECT a.garmin_user_id IS NOT NULL, c.subject IS NOT NULL
            FROM garminai.athletes a LEFT JOIN garminai.garmin_credentials c
            ON a.subject=c.subject WHERE a.subject=%s''',(principal.subject,))
        row=cur.fetchone()
        return {'linked':bool(row and row[0] and row[1]),'activities_access':False,'ai_sharing':False}


def _principal_from_context(ctx):
    try: p=ctx.request_context.request.scope.get('garminai.verified_garmin_principal')
    except (ValueError,AttributeError,TypeError): p=None
    if not isinstance(p,VerifiedPrincipal): raise PermissionError('NEON_LOGIN_REQUIRED')
    return p


def _assert_database_ready(principal):
    # Operator read-only check: no link may be offered before the replay table
    # and all required RLS policies are present in the actual Neon database.
    with _db_cursor(principal) as cur:
        cur.execute("""SELECT c.relname,c.relrowsecurity,c.relforcerowsecurity
                 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                 WHERE n.nspname='garminai' AND c.relname IN
                 ('garmin_oauth_used_states','athletes','garmin_credentials')""")
        flags={name:(rls,forced) for name,rls,forced in cur.fetchall()}
        if set(flags) != {'garmin_oauth_used_states','athletes','garmin_credentials'} or \
           any(not rls or not forced for rls,forced in flags.values()):
            raise PermissionError('GARMIN_RLS_NOT_READY')


def connect_link_from_context(ctx):
    """MCP tool body: only verified Neon subject; never accepts user ID."""
    c=configuration()
    if not c['enabled']: return {'status':'NOT_ENABLED','message':'Garmin OAuth staging is not enabled by operator'}
    p=_principal_from_context(ctx)
    try: _assert_database_ready(p)
    except Exception: return {'status':'STORAGE_NOT_READY','message':'Check Neon staging migration and app RLS role before enabling Garmin linking.'}
    ticket=issue_ticket(p,key=load_key())
    return {'status':'READY_FOR_USER_CONFIRMATION','url':BASE+'/garmin/oauth/connect?ticket='+ticket,
            'expires_in_seconds':600,'message':'Open link privately; confirm in browser. Never share the link. No data is shared with ChatGPT.'}


def status_from_context(ctx):
    c=configuration()
    if not c['enabled']: return {'status':'NOT_ENABLED','linked':False}
    p=_principal_from_context(ctx)
    try: return {'status':'STAGING_ONLY',**_link_status(p)}
    except Exception: return {'status':'STORAGE_NOT_READY','linked':False}


def _page(message, status=200):
    import html
    markup='''<!doctype html><html lang="sr"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>GarminAI Connect</title>
    <style>body{background:#0b1220;color:#fff;font:16px system-ui;display:grid;place-items:center;min-height:100vh}main{background:#172538;border:1px solid #40516b;border-radius:14px;padding:32px;max-width:520px}p{line-height:1.6}button{background:#157963;color:#fff;border:0;border-radius:8px;padding:12px 18px;cursor:pointer}</style>
    <main><h1>GarminAI · Garmin Connect</h1><p>'''+html.escape(message)+'''</p></main></html>'''
    return HTMLResponse(markup,status_code=status,headers=_HTML_HEADERS)


async def start_page(request):
    c=configuration()
    if not c['enabled']: return _page('Povezivanje Garmin naloga još nije aktivirano.',503)
    q=request.query_params
    ticket=q.get('ticket','')
    try: validate_ticket(ticket,key=load_key())
    except (ValueError,TypeError): return _page('Link je nevažeći ili je istekao.',400)
    csrf=secrets.token_urlsafe(32)
    import html
    body='''<!doctype html><html lang="sr"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Potvrdi Garmin povezivanje</title>
    <style>body{background:#0b1220;color:#fff;font:16px system-ui;display:grid;place-items:center;min-height:100vh}main{background:#172538;border:1px solid #40516b;border-radius:14px;padding:32px;max-width:560px}p{line-height:1.6}button{background:#157963;color:#fff;border:0;border-radius:8px;padding:12px 18px;cursor:pointer}</style><main>
    <h1>Poveži Garmin Connect</h1><p>Ovim pokrećeš Garmin prijavu. Nakon tvoje saglasnosti aplikacija čuva šifrovane tokene i Garmin ID za povezivanje naloga.</p>
    <p><strong>Nove Garmin aktivnosti se još ne preuzimaju i ne šalju ChatGPT-u.</strong> Bez omogućene posebne integracije nema deljenja stvarnih podataka sa AI.</p>
    <p>Vezu možeš prekinuti u Garmin Connect podešavanjima. Ne deli ovaj privatni link.</p>
    <form action="/garmin/oauth/authorize" method="post"><input type="hidden" name="ticket" value="'''+html.escape(ticket,quote=True)+'''"><input type="hidden" name="csrf" value="'''+html.escape(csrf,quote=True)+'''"><button type="submit">Nastavi na Garmin</button></form></main></html>'''
    response=HTMLResponse(body,headers=_CONNECT_HEADERS)
    response.set_cookie(COOKIE,csrf,max_age=600,httponly=True,secure=True,samesite='lax',path='/')
    return response


async def authorize(request):
    if not configuration()['enabled']: return _page('Povezivanje nije aktivirano.',503)
    if request.headers.get('content-type','').split(';')[0].lower() != 'application/x-www-form-urlencoded':
        return _page('Pogrešan tip zahteva.',400)
    try:
        raw=await request.body()
        if not 1 <= len(raw) <= 3000: raise ValueError()
        form=parse_qs(raw.decode('ascii'), strict_parsing=True)
        ticket,csrf=form['ticket'],form['csrf']
        if len(ticket)!=1 or len(csrf)!=1: raise ValueError()
        val=validate_ticket(ticket[0],key=load_key())
        if not hmac.compare_digest(csrf[0],request.cookies.get(COOKIE,'')) or not csrf[0]: raise ValueError()
        principal=principal_from_sealed_link(val['subject'])
        attempt=create_authorization_attempt()
        browser=secrets.token_urlsafe(32)
        state=make_state(principal,attempt.verifier,browser,key=load_key())
        url=build_authorization_url(os.environ['GARMIN_CLIENT_ID'],CALLBACK,attempt)
        # Build URL with our encrypted browser-bound state, not the default attempt.state.
        parts=urlsplit(url)
        fields=[(k,(state if k=='state' else v)) for k,v in parse_qsl(parts.query)]
        url=urlunsplit((parts.scheme,parts.netloc,parts.path,urlencode(fields),''))
    except (ValueError,KeyError,TypeError,PermissionError):
        return _page('Nije moguće pokrenuti OAuth. Otvori nov link iz ChatGPT-a.',400)
    response=RedirectResponse(url,status_code=303,headers=_SAFE_HEADERS)
    response.set_cookie(OAUTH_COOKIE,browser,max_age=600,httponly=True,secure=True,samesite='lax',path='/')
    response.delete_cookie(COOKIE,path='/')
    return response


def _permission_list(obj):
    if isinstance(obj,list) and all(isinstance(v,str) for v in obj): return obj
    if isinstance(obj,dict) and isinstance(obj.get('permissions'),list) and all(isinstance(v,str) for v in obj['permissions']):
        return obj['permissions']
    raise ValueError('UNKNOWN_PERMISSIONS_RESPONSE')


async def callback(request):
    if not configuration()['enabled']: return _page('Garmin OAuth je i dalje isključen.',503)
    if request.query_params.get('error'): return _page('Garmin povezivanje je odbijeno. Nema nove veze.',400)
    if len(request.query_params.getlist('code')) != 1 or len(request.query_params.getlist('state')) != 1:
        return _page('Nepotpuni Garmin callback.',400)
    code,state=request.query_params['code'],request.query_params['state']
    if not _CODE_CHARS.fullmatch(code): return _page('Nevažeći autorizacioni kod.',400)
    try:
        stored=validate_state(state,request.cookies.get(OAUTH_COOKIE,''),key=load_key())
        principal=principal_from_sealed_link(stored['subject'])
        # Atomic durable one-time use BEFORE exchanging credentials; replay cannot repeat requests.
        import asyncio
        await asyncio.to_thread(_consume_callback,principal,state)
    except (ValueError,PermissionError,TypeError,KeyError):
        return _page('OAuth sesija je nevažeća, iskorišćena ili istekla.',400)
    except Exception:
        return _page('Bezbedno povezivanje nije dostupno (baza). Pokušaj novi link kasnije.',503)
    token=None
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(15.0,connect=5.0),follow_redirects=False,trust_env=False) as client:
            token=await exchange_code(client,client_id=os.environ['GARMIN_CLIENT_ID'],
                client_secret=os.environ['GARMIN_CLIENT_SECRET'], code=code,
                verifier=stored['verifier'], redirect_uri=CALLBACK)
            uid=await garmin_user_id(client,token['access_token'])
            permissions=_permission_list(await garmin_permissions(client,token['access_token']))
        await asyncio.to_thread(_store_link,principal,uid,token,permissions,load_key())
    except Exception as error:
        # Best-effort compensation if Garmin granted consent but local binding
        # or Activity Export permission validation failed. Never log/echo token.
        if isinstance(token,dict) and isinstance(token.get('access_token'),str):
            try:
                async with httpx.AsyncClient(timeout=8.0,follow_redirects=False,trust_env=False) as cleanup:
                    await cleanup.delete('https://apis.garmin.com/wellness-api/rest/user/registration',
                            headers={'Authorization':'Bearer '+token['access_token']})
            except Exception: pass
        if isinstance(error, PermissionError):
            return _page('Garmin nalog nije povezan. Proveri Activity Export dozvolu i po potrebi ukloni GarminAI iz Garmin Connect dozvoljenih aplikacija.',403)
        return _page('Garmin povezivanje nije završeno. Proveri Garmin Connect dozvole; nisu uključeni stvarni podaci u ChatGPT-u.',503)
    response=_page('Garmin nalog je povezan. Prijem aktivnosti i AI obrada ostaju isključeni.')
    response.delete_cookie(OAUTH_COOKIE,path='/')
    return response


def _read_credentials(principal, key):
    with _db_cursor(principal) as cur:
        cur.execute("""SELECT a.garmin_user_id,c.nonce,c.encrypted_blob
            FROM garminai.athletes a JOIN garminai.garmin_credentials c ON a.subject=c.subject
            WHERE a.subject=%s""",(principal.subject,))
        row=cur.fetchone()
    if not row: return None
    raw=TokenVault(key).open(principal,bytes(row[1]),bytes(row[2]))
    payload=json.loads(raw)
    if not isinstance(payload,dict) or not hmac.compare_digest(payload.get('garmin_user_id',''),row[0]):
        raise ValueError('STORED_GARMIN_LINK_INVALID')
    return payload


def _rotate_stored_tokens(principal, replacement, key):
    # Validate then atomically store new refresh token with a subject-bound write.
    existing=_read_credentials(principal,key)
    if existing is None: raise ValueError('NO_LINK')
    existing['access_token']=replacement['access_token']
    existing['refresh_token']=replacement['refresh_token']
    existing['expires_at']=int(time.time())+int(replacement['expires_in'])
    nonce,blob=TokenVault(key).seal(principal,json.dumps(existing,separators=(',',':')).encode())
    with _db_cursor(principal) as cur:
        cur.execute('UPDATE garminai.garmin_credentials SET nonce=%s, encrypted_blob=%s, updated_at=now() WHERE subject=%s',
                    (nonce,blob,principal.subject))
        if cur.rowcount != 1: raise ValueError('NO_LINK')


def _forget_link(principal):
    with _db_cursor(principal) as cur:
        cur.execute('DELETE FROM garminai.garmin_credentials WHERE subject=%s',(principal.subject,))
        cur.execute('UPDATE garminai.athletes SET garmin_user_id=NULL WHERE subject=%s',(principal.subject,))
        # Future data ingestion is still disabled; any data already stored is
        # removed when this user explicitly disconnects.
        cur.execute('DELETE FROM garminai.activities WHERE subject=%s',(principal.subject,))


async def disconnect_from_context(ctx, confirmation):
    """Explicit revoke at Garmin, followed by tenant-local encrypted-data deletion."""
    if confirmation != 'DISCONNECT_GARMIN':
        return {'status':'CONFIRMATION_REQUIRED','message':'Explicitly confirm DISCONNECT_GARMIN before revocation.'}
    if not configuration()['enabled']:
        return {'status':'NOT_ENABLED','message':'Garmin linking is disabled'}
    principal=_principal_from_context(ctx)
    import asyncio
    key=load_key()
    try: saved=await asyncio.to_thread(_read_credentials,principal,key)
    except Exception: return {'status':'DATABASE_UNAVAILABLE'}
    if saved is None: return {'status':'ALREADY_DISCONNECTED'}
    try:
        token=saved['access_token']
        async with httpx.AsyncClient(timeout=httpx.Timeout(15.0,connect=5.0),follow_redirects=False,trust_env=False) as client:
            if saved.get('expires_at',0) <= time.time()+60:
                replacement=await refresh_access(client,client_id=os.environ['GARMIN_CLIENT_ID'],
                         client_secret=os.environ['GARMIN_CLIENT_SECRET'],refresh_token=saved['refresh_token'])
                if (not isinstance(replacement.get('expires_in'),int) or
                        not isinstance(replacement.get('access_token'),str) or
                        not isinstance(replacement.get('refresh_token'),str)):
                    raise ValueError('INVALID_REFRESH')
                await asyncio.to_thread(_rotate_stored_tokens,principal,replacement,key)
                token=replacement['access_token']
            response=await client.delete('https://apis.garmin.com/wellness-api/rest/user/registration',
                                        headers={'Authorization':'Bearer '+token},timeout=15.0)
            response.raise_for_status()
        await asyncio.to_thread(_forget_link,principal)
        return {'status':'DISCONNECTED','garmin_access_revoked':True,'local_data_deleted':True}
    except Exception:
        # Do not misrepresent remote revocation, or silently delete local data
        # when user has requested a Garmin-side disconnect as well.
        return {'status':'REVOKE_UNCONFIRMED','message':'Try again or revoke GarminAI in Garmin Connect settings.'}
