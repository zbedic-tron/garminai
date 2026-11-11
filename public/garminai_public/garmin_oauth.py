"""Garmin Business OAuth 2.0 + PKCE protocol primitives.

Staging-only. NO public account-connect flow is enabled in v0.5. Never log
code verifier, authorization code, client secret, access or refresh tokens.
Official parameters/URLs must be checked against the current Garmin portal.
"""
import base64
import hashlib
import hmac
import secrets
import time
from dataclasses import dataclass
from urllib.parse import urlencode
import httpx

GARMIN_AUTHORIZE_URL = 'https://connect.garmin.com/oauth2Confirm'
GARMIN_TOKEN_URL = 'https://diauth.garmin.com/di-oauth2-service/oauth/token'
GARMIN_ID_URL = 'https://apis.garmin.com/wellness-api/rest/user/id'
GARMIN_PERMISSIONS_URL = 'https://apis.garmin.com/wellness-api/rest/user/permissions'

@dataclass(frozen=True)
class AuthorizationAttempt:
    state: str
    verifier: str
    challenge: str
    created_at: int

def create_authorization_attempt(now=None):
    verifier = secrets.token_urlsafe(64)  # RFC 7636, 86 chars
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode('ascii')).digest()).rstrip(b'=').decode('ascii')
    return AuthorizationAttempt(secrets.token_urlsafe(32), verifier, challenge, int(time.time() if now is None else now))

def build_authorization_url(client_id, redirect_uri, attempt):
    if not client_id or not redirect_uri.startswith('https://'):
        raise ValueError('Client ID and HTTPS registered redirect URI required')
    if not isinstance(attempt, AuthorizationAttempt):
        raise TypeError('An authorization attempt is required')
    return GARMIN_AUTHORIZE_URL + '?' + urlencode({
        'response_type':'code','client_id':client_id,'redirect_uri':redirect_uri,
        'code_challenge':attempt.challenge,'code_challenge_method':'S256','state':attempt.state})

def validate_callback_state(attempt, received_state, now=None, ttl_seconds=600):
    if not isinstance(attempt, AuthorizationAttempt) or not isinstance(received_state,str):
        return False
    if not hmac.compare_digest(attempt.state, received_state):
        return False
    current = int(time.time() if now is None else now)
    return 0 <= current-attempt.created_at <= ttl_seconds

def _require_confidential(client_id,client_secret):
    if not client_id or not client_secret:
        raise ValueError('Missing confidential Garmin client credentials')

async def exchange_code(client, *, client_id, client_secret, code, verifier, redirect_uri):
    """Exchange a code through injected HTTP client. Caller owns durable state and encryption."""
    _require_confidential(client_id, client_secret)
    if not code or not verifier or not redirect_uri.startswith('https://'):
        raise ValueError('Incomplete authorization code exchange')
    response = await client.post(GARMIN_TOKEN_URL,data={
        'grant_type':'authorization_code','client_id':client_id,'client_secret':client_secret,
        'code':code,'code_verifier':verifier,'redirect_uri':redirect_uri,
    },headers={'Accept':'application/json'},timeout=15.0)
    response.raise_for_status()
    token=response.json()
    if not all(isinstance(token.get(k),str) and token[k] for k in ('access_token','refresh_token')):
        raise ValueError('Garmin token response missing required fields')
    return token

async def refresh_access(client, *, client_id,client_secret,refresh_token):
    _require_confidential(client_id,client_secret)
    if not refresh_token: raise ValueError('Missing refresh token')
    response=await client.post(GARMIN_TOKEN_URL,data={
        'grant_type':'refresh_token','client_id':client_id,
        'client_secret':client_secret,'refresh_token':refresh_token,
    },headers={'Accept':'application/json'},timeout=15.0)
    response.raise_for_status()
    data=response.json()
    if not isinstance(data.get('access_token'),str) or not isinstance(data.get('refresh_token'),str):
        raise ValueError('Garmin response must contain rotated refresh token')
    return data

async def garmin_user_id(client, access_token):
    if not access_token:raise ValueError('Missing token')
    response=await client.get(GARMIN_ID_URL,headers={'Authorization':'Bearer '+access_token,'Accept':'application/json'},timeout=15.0)
    response.raise_for_status()
    user_id=response.json().get('userId')
    if not isinstance(user_id,str) or not user_id or len(user_id)>256:
        raise ValueError('Garmin user ID missing')
    return user_id

async def garmin_permissions(client, access_token):
    if not access_token:raise ValueError('Missing token')
    response=await client.get(GARMIN_PERMISSIONS_URL,headers={'Authorization':'Bearer '+access_token,'Accept':'application/json'},timeout=15.0)
    response.raise_for_status()
    return response.json()
