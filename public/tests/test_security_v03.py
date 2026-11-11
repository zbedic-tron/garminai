import asyncio
import hashlib
import pytest
from garminai_public.auth_gate import authorize, DemoBearerGate
from garminai_public.tenant_store import Principal, IsolatedActivityStore
from garminai_public.literature_search import rank_sources
from garminai_public import core

TOKEN = 'test_' + 'x'*45
DIGEST = hashlib.sha256(TOKEN.encode()).hexdigest()

def test_gate_closed_without_configuration():
    assert authorize([(b'authorization', ('Bearer '+TOKEN).encode())], '') == (False, 503)

def test_gate_rejects_missing_and_bad_token():
    assert authorize([], DIGEST) == (False, 401)
    assert authorize([(b'authorization',b'Bearer bad')],DIGEST) == (False,401)

def test_gate_accepts_valid_and_rejects_duplicate_headers():
    header=(b'authorization', ('Bearer '+TOKEN).encode())
    assert authorize([header],DIGEST) == (True,200)
    assert authorize([header,header],DIGEST) == (False,401)

def test_users_cannot_read_each_others_rows():
    a,b=Principal('athlete-a'),Principal('athlete-b')
    store=IsolatedActivityStore()
    store.add(a,'run-1',{'km':10})
    store.add(b,'run-1',{'km':5})
    assert store.get(a,'run-1') == {'km':10}
    assert store.get(b,'run-1') == {'km':5}
    assert store.list(a) == [{'km':10}]
    assert store.list(b) == [{'km':5}]
    assert store.get(a,'run-2') is None
    with pytest.raises(PermissionError): store.get(None,'run-1')

def test_literature_only_approved_and_relevant():
    items=[{'title':'Running intensity study','topic':['intensity'],'year':2024},
           {'title':'Economic growth','topic':['finance'],'year':2025}]
    assert len(rank_sources(items,'intensity'))==1
    results=core.literature('intensity')
    assert all('intensity' in ' '.join(i.get('topic',[])).lower() or 'intensity' in i.get('title','').lower() or 'intensity' in i.get('note_sr','').lower() for i in results['sources'])

async def invoke_gate(headers, configured):
    from unittest.mock import patch
    called=[]; events=[]
    async def inner(scope,receive,send):
        called.append(True)
        await send({'type':'http.response.start','status':200,'headers':[]})
        await send({'type':'http.response.body','body':b'ok'})
    async def receive(): return {'type':'http.request','body':b'', 'more_body':False}
    async def send(msg):events.append(msg)
    with patch.dict('os.environ', {'GARMINAI_DEMO_TOKEN_SHA256':configured},clear=False):
        await DemoBearerGate(inner)({'type':'http','headers':headers,'method':'POST','path':'/mcp'},receive,send)
    return called,events

def test_asgi_blocks_unauthenticated_requests():
    called, events = asyncio.run(invoke_gate([],DIGEST))
    assert not called and events[0]['status']==401

def test_asgi_forwards_authorized_requests():
    h=[(b'authorization',('Bearer '+TOKEN).encode())]
    called, events = asyncio.run(invoke_gate(h,DIGEST))
    assert called and events[0]['status']==200
