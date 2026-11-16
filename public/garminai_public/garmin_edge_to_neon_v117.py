"""v1.1.7 opt-in SYNTHETIC Cloudflare D1 -> Neon inbox delivery.

ONLY called inside the subject-verified MCP tool, never via a public HTTP route.
One fixed fictional receipt per verified subject; not Garmin sender verification,
not an Activity API connector, not a real-data AI pipeline. Render pulls D1:
D1 seed -> claim and verify -> Neon transaction COMMIT -> D1 ack.
If D1 ack fails after Neon commit, rerun safely deduplicates in Neon.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
from urllib.parse import urlsplit

from .garmin_activity_staging import TrustedOwnerBinding, parse_activity_push, prepare_for_owner
from .garmin_push_inbox_v111 import OfflinePostgresPushInbox
from .garmin_push_rehearsal_v110 import PushConflictingReplay, PushOwnershipRejected, PushStorageUnavailable
from .identity import VerifiedPrincipal

CONFIRM = 'RUN_SYNTHETIC_EDGE_TO_NEON'
PREFIX = 'SYNTHETIC_BRIDGE_V117_'
KIND = 'SYNTHETIC_BRIDGE'
FIXTURE_START = 1794650000
WORKER_HOST = 'garminai-synthetic-edge-v116.zbedic.workers.dev'


class EdgeBridgeError(Exception):
    """Safe abstract error. Remote responses, URLs and secrets must not escape."""


def _bridge_config(env):
    token = env.get('GARMINAI_EDGE_BRIDGE_TOKEN', '')
    url = env.get('GARMINAI_EDGE_BRIDGE_URL', '')
    if not isinstance(token, str) or not re.fullmatch(r'[A-Za-z0-9_-]{40,128}', token):
        return None
    if not isinstance(url, str):
        return None
    try:
        parsed = urlsplit(url)
        # No HTTP, user info, redirects, query string, fragment, internal IP or ports.
        if parsed.scheme != 'https' or parsed.hostname != WORKER_HOST or parsed.port is not None or \
                parsed.username is not None or parsed.password is not None or parsed.path not in ('', '/') or \
                parsed.query or parsed.fragment or parsed.netloc != WORKER_HOST:
            return None
    except (ValueError, AttributeError):
        return None
    return url.rstrip('/'), token


def recipient_for(principal: VerifiedPrincipal, token: str) -> tuple[str, str]:
    if not isinstance(principal, VerifiedPrincipal) or not isinstance(token, str) or len(token) < 40:
        raise ValueError('Verified subject and bridge secret required')
    tenant = hmac.new(token.encode(),
        b'garminai-v117-tenant\x00' + principal.subject.encode(), hashlib.sha256).hexdigest()
    event = hmac.new(token.encode(),
        b'garminai-v117-event\x00' + tenant.encode(), hashlib.sha256).hexdigest()[:32]
    return tenant, PREFIX + event


def _digest(tenant: str, event: str) -> str:
    return hashlib.sha256((tenant+'\x00'+event+'\x00'+KIND).encode()).hexdigest()


class EdgeBridgeClient:
    """Outbound-only HTTPS, strict response checking, no redirects and no logs."""
    def __init__(self, url, token, *, client_factory=None):
        self.url, self.token = url, token
        self.client_factory = client_factory

    def exchange(self, action: str, tenant: str, event: str) -> dict:
        if action not in ('seed', 'claim', 'ack'):
            raise EdgeBridgeError('INVALID_ACTION')
        import httpx
        client_factory = self.client_factory or (lambda: httpx.Client(
            timeout=httpx.Timeout(9.0), follow_redirects=False, trust_env=False))
        try:
            with client_factory() as client:
                response = client.post(self.url + '/_lab/bridge/' + action,
                    json={'kind':KIND,'recipient_key':tenant,'event_id':event},
                    headers={'x-bridge-token':self.token, 'accept':'application/json'})
            if response.status_code != 200:
                raise EdgeBridgeError('EDGE_HTTP_NOT_READY')
            if len(response.content) > 2048 or response.headers.get('content-type','').split(';',1)[0].lower() != 'application/json':
                raise EdgeBridgeError('EDGE_INVALID_RESPONSE')
            data = response.json()
            if (not isinstance(data, dict) or
                    data.get('mode') != 'SYNTHETIC_BRIDGE_ONLY' or
                    data.get('event_id') != event or
                    not isinstance(data.get('payload_digest'),str) or
                    not re.fullmatch(r'[0-9a-f]{64}',data['payload_digest']) or
                    type(data.get('acknowledged')) is not bool or
                    data.get('status') not in ('PENDING_SYNTHETIC','ACKED_SYNTHETIC') or
                    (data['status'] == 'ACKED_SYNTHETIC') != data['acknowledged']):
                raise EdgeBridgeError('EDGE_INVALID_RECEIPT')
            return data
        except EdgeBridgeError:
            raise
        except Exception as exc:
            # Deliberately never include exception text: can contain token or URL.
            raise EdgeBridgeError('EDGE_UNREACHABLE') from exc


def _linked_user_id(principal):
    from .garmin_push_e2e_v112 import _linked_user_id as read_verified_link
    return read_verified_link(principal)


def deliver_for_principal(principal, confirmation, *, env=None, lookup=None, store=None, edge=None) -> dict:
    """Single subject-scoped bridge rehearsal with explicit consent and opt-in.

    Optional injections are for unit tests only; production always resolves
    linked Garmin identity from the server-side RLS store.
    """
    if not isinstance(principal, VerifiedPrincipal):
        return {'status':'NEON_AUTH_REQUIRED'}
    if confirmation != CONFIRM:
        return {'status':'CONFIRMATION_REQUIRED','required':CONFIRM,
                'effect':'At most one fictional delivery receipt in D1 and one fictional summary in Neon per authenticated subject.'}
    e = os.environ if env is None else env
    if e.get('GARMINAI_EDGE_BRIDGE_STAGING_ENABLED') != '1':
        return {'status':'OPERATOR_DISABLED'}
    config = _bridge_config(e)
    if config is None:
        return {'status':'EDGE_BRIDGE_CONFIG_NOT_READY'}
    url, token = config
    try:
        user_id = (lookup or _linked_user_id)(principal)
        if not isinstance(user_id,str) or not user_id:
            return {'status':'GARMIN_LINK_REQUIRED'}
        owner = TrustedOwnerBinding(principal,user_id)
        tenant, event_id = recipient_for(principal,token)
        expected_digest = _digest(tenant,event_id)
        bridge = edge or EdgeBridgeClient(url,token)
        for action in ('seed','claim'):
            receipt = bridge.exchange(action,tenant,event_id)
            if not hmac.compare_digest(receipt['payload_digest'],expected_digest):
                return {'status':'EDGE_RECEIPT_MISMATCH'}
        # Only synthetic constants are projected into the existing RLS inbox.
        # Crucially, no Cloudflare-provided userId or workout content is used.
        body = json.dumps({'activities':[{
            'userId':user_id,'summaryId':event_id,'activityType':'RUNNING',
            'startTimeInSeconds':FIXTURE_START,'durationInSeconds':1200,
            'distanceInMeters':4000.0
        }]}).encode('utf-8')
        batch = prepare_for_owner(owner,parse_activity_push(body,'application/json'))
        inbox = store or OfflinePostgresPushInbox()
        first = inbox.enqueue_offline_verified_fixture(owner,batch)
        second = inbox.enqueue_offline_verified_fixture(owner,batch)
        if ((first.enqueued,first.duplicates) not in ((1,0),(0,1)) or
                (second.enqueued,second.duplicates) != (0,1)):
            return {'status':'NEON_INBOX_CHECK_FAILED'}
        try:
            ack = bridge.exchange('ack',tenant,event_id)
            if not hmac.compare_digest(ack['payload_digest'],expected_digest) or not ack['acknowledged']:
                return {'status':'NEON_COMMITTED_EDGE_ACK_PENDING','retry_safe':True}
        except EdgeBridgeError:
            return {'status':'NEON_COMMITTED_EDGE_ACK_PENDING','retry_safe':True}
        return {'status':'PASS','mode':'SYNTHETIC_EDGE_TO_NEON_ONLY',
                'd1_durable_receipt':True,'neon_committed_or_existing':True,
                'neon_duplicate_prevented':True,'d1_acknowledged':True,
                'scoped_by_verified_neon_subject':True,'synthetic_limit_per_subject':1,
                'real_activities_read':False,'garmin_push_enabled':False,
                'ai_sharing_enabled':False}
    except EdgeBridgeError:
        return {'status':'EDGE_NOT_READY','retry_safe':True}
    except (PushConflictingReplay,PushOwnershipRejected,PushStorageUnavailable,ValueError,PermissionError):
        return {'status':'NEON_WRITE_NOT_CONFIRMED','retry_safe':True}
    except Exception:
        return {'status':'BRIDGE_CHECK_NOT_READY','retry_safe':True}


def deliver_from_context(ctx,confirmation):
    from .garmin_link_v101 import _principal_from_context
    return deliver_for_principal(_principal_from_context(ctx),confirmation)
