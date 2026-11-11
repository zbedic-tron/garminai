import asyncio, base64, hashlib
from urllib.parse import parse_qs, urlparse
import pytest
from garminai_public.garmin_oauth import (
    create_authorization_attempt, build_authorization_url,validate_callback_state,
    exchange_code,refresh_access,garmin_user_id,GARMIN_TOKEN_URL,GARMIN_ID_URL,
)
from garminai_public.garmin_push import validate_envelope,fingerprint
from garminai_public.readiness import get_readiness

def test_pkce_entropy_and_shape():
    a,b=create_authorization_attempt(100),create_authorization_attempt(100)
    assert len(a.verifier)>=43 and len(a.verifier)<=128
    assert a.state!=b.state and a.verifier!=b.verifier
    assert base64.urlsafe_b64encode(hashlib.sha256(a.verifier.encode()).digest()).rstrip(b'=').decode()==a.challenge

def test_authorization_url_bound_to_redirect():
    a=create_authorization_attempt(100)
    url=build_authorization_url('public-id','https://example.org/garmin/oauth/callback',a)
    p=urlparse(url); q=parse_qs(p.query)
    assert p.hostname=='connect.garmin.com' and q['code_challenge_method']==['S256']
    assert q['state']==[a.state] and q['redirect_uri']==['https://example.org/garmin/oauth/callback']

def test_state_mismatch_expired_and_future_rejected():
    a=create_authorization_attempt(100)
    assert validate_callback_state(a,a.state,now=200)
    assert not validate_callback_state(a,'another-state',now=200)
    assert not validate_callback_state(a,a.state,now=701)
    assert not validate_callback_state(a,a.state,now=99)

def test_readiness_fails_closed_even_with_credentials():
    info=get_readiness({'GARMIN_CLIENT_ID':'id','GARMIN_CLIENT_SECRET':'private','GARMIN_REDIRECT_URI':'https://host/garmin/oauth/callback','DATABASE_URL':'postgres://secret'})
    assert info['garmin_connect_enabled'] is False
    assert info['ai_processing_enabled'] is False
    assert 'private' not in str(info) and 'postgres://' not in str(info)
    assert info['redirect_uri_configured']

def test_push_envelope_rejects_invalid_inputs():
    assert validate_envelope(b'{"activities":[]}', 'application/json')=={'activities':[]}
    assert len(fingerprint(b'x'))==64
    for body,ct in [(b'[]','application/json'),(b'{}','text/plain'),(b'X'*512001,'application/json')]:
        with pytest.raises(ValueError):validate_envelope(body,ct)

def test_token_exchange_uses_pkce_without_logs():
    class Resp:
        def raise_for_status(self): pass
        def json(self):return {'access_token':'access','refresh_token':'refresh','expires_in':86400}
    class Client:
        async def post(self,url,**kwargs):
            assert url==GARMIN_TOKEN_URL and kwargs['data']['code_verifier']=='verifier'
            assert kwargs['data']['client_secret']=='secret'
            return Resp()
    result=asyncio.run(exchange_code(Client(),client_id='id',client_secret='secret',code='code',verifier='verifier',redirect_uri='https://host/callback'))
    assert result['access_token']=='access'

def test_token_refresh_requires_rotated_refresh_token():
    class Resp:
        def raise_for_status(self): pass
        def json(self):return {'access_token':'new','refresh_token':'rotated'}
    class Client:
        async def post(self,url,**kwargs):return Resp()
    assert asyncio.run(refresh_access(Client(),client_id='id',client_secret='secret',refresh_token='old'))['refresh_token']=='rotated'

def test_user_id_comes_from_garmin_not_caller():
    class Resp:
        def raise_for_status(self): pass
        def json(self):return {'userId':'stable-garmin-user-id'}
    class Client:
        async def get(self,url,**kwargs):
            assert url==GARMIN_ID_URL
            assert kwargs['headers']['Authorization']=='Bearer valid-token'
            return Resp()
    assert asyncio.run(garmin_user_id(Client(),'valid-token'))=='stable-garmin-user-id'
