"""v1.1.8 strictly fictional, operator-controlled D1 -> Neon recovery laboratory.

No real Garmin messages, no public Render write route, no scheduled polling.
Fault scenarios SKIP designated stages intentionally; they do NOT crash Neon,
Cloudflare, Render, or verify any production SLA. One new fixed event per
verified OAuth subject. The pre-existing v1.1.7 receipt is never mutated.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re

from .garmin_activity_staging import TrustedOwnerBinding, parse_activity_push, prepare_for_owner
from .garmin_edge_to_neon_v117 import _bridge_config, recipient_for, _linked_user_id
from .garmin_push_inbox_v111 import OfflinePostgresPushInbox
from .garmin_push_rehearsal_v110 import PushConflictingReplay, PushOwnershipRejected, PushStorageUnavailable
from .identity import VerifiedPrincipal

CONFIRM = 'RUN_SYNTHETIC_DELIVERY_RECOVERY'
SCENARIOS = frozenset(('SIMULATE_RENDER_DELAY', 'SIMULATE_NEON_UNAVAILABLE',
                       'SIMULATE_D1_ACK_UNAVAILABLE', 'RECOVER'))
PREFIX = 'SYNTHETIC_RECOVERY_V118_'
KIND = 'SYNTHETIC_RECOVERY'
FIXTURE_START = 1794656000
MODE = 'SYNTHETIC_RECOVERY_ONLY'


class RecoveryError(Exception):
    """Safe exception; no secrets or remote body exposed."""


def recipient_for_recovery(principal: VerifiedPrincipal, token: str) -> tuple[str, str]:
    tenant, _ = recipient_for(principal, token)
    event = hmac.new(token.encode('utf-8'),
                     b'garminai-v118-recovery-event\x00' + tenant.encode('ascii'),
                     hashlib.sha256).hexdigest()[:32]
    return tenant, PREFIX + event


def recovery_digest(tenant: str, event: str) -> str:
    return hashlib.sha256((tenant + '\x00' + event + '\x00' + KIND).encode('ascii')).hexdigest()


class RecoveryEdgeClient:
    """Render -> pinned HTTPS Worker only, no redirects, proxy or DNS override."""
    def __init__(self, url, token, *, client_factory=None):
        self.url, self.token, self.client_factory = url, token, client_factory

    def exchange(self, action: str, tenant: str, event: str):
        if action not in ('seed', 'claim', 'ack', 'inspect'):
            raise RecoveryError('INVALID_ACTION')
        import httpx
        factory = self.client_factory or (lambda: httpx.Client(
            timeout=httpx.Timeout(9.0), follow_redirects=False, trust_env=False))
        try:
            with factory() as client:
                response = client.post(self.url + '/_lab/recovery/' + action,
                    headers={'x-bridge-token': self.token, 'accept': 'application/json'},
                    json={'kind': KIND, 'recipient_key': tenant, 'event_id': event})
            if response.status_code == 404 and action == 'inspect':
                # A missing *receipt* is not the same as an obsolete Worker
                # that has never heard of /_lab/recovery/inspect.
                if (len(response.content) <= 2048 and
                        response.headers.get('content-type','').split(';',1)[0].lower() == 'application/json'):
                    missing = response.json()
                    if (isinstance(missing, dict) and missing.get('mode') == MODE and
                            missing.get('status') == 'SYNTHETIC_EVENT_NOT_FOUND'):
                        return None
                raise RecoveryError('EDGE_RECOVERY_ROUTE_MISSING')
            if response.status_code != 200:
                raise RecoveryError('EDGE_NOT_READY')
            if (len(response.content) > 2048 or
                    response.headers.get('content-type', '').split(';', 1)[0].lower() != 'application/json'):
                raise RecoveryError('EDGE_INVALID_RESPONSE')
            data = response.json()
            if (not isinstance(data, dict) or
                    data.get('mode') != MODE or
                    data.get('event_id') != event or
                    type(data.get('acknowledged')) is not bool or
                    type(data.get('attempts')) is not int or
                    not 0 <= data['attempts'] <= 1000000 or
                    data.get('status') not in ('PENDING_SYNTHETIC', 'ACKED_SYNTHETIC') or
                    (data['status'] == 'ACKED_SYNTHETIC') != data['acknowledged'] or
                    not isinstance(data.get('payload_digest'), str) or
                    not re.fullmatch('[0-9a-f]{64}', data['payload_digest'])):
                raise RecoveryError('EDGE_INVALID_RECEIPT')
            return data
        except RecoveryError:
            raise
        except Exception as exc:
            raise RecoveryError('EDGE_UNREACHABLE') from exc


def _check_receipt(receipt, tenant, event):
    if receipt is None or not hmac.compare_digest(receipt['payload_digest'], recovery_digest(tenant, event)):
        raise RecoveryError('EDGE_RECEIPT_MISMATCH')
    return receipt


def _safe_status(acknowledged, attempts):
    return {'status': 'ACKED_SYNTHETIC' if acknowledged else 'PENDING_SYNTHETIC',
            'mode': MODE, 'd1_acknowledged': acknowledged,
            'd1_claim_attempts': attempts,
            'real_garmin_activities_used': False,
            'garmin_push_enabled': False, 'ai_data_sharing_enabled': False,
            'subject_scoped': True,
            'neon_independently_queried': False}


def status_for_principal(principal, *, env=None, edge=None):
    """Subject-scoped, READ ONLY D1 state; no AI or Garmin data ever returned."""
    if not isinstance(principal, VerifiedPrincipal):
        return {'status': 'NEON_AUTH_REQUIRED'}
    e = os.environ if env is None else env
    cfg = _bridge_config(e)
    if cfg is None:
        return {'status': 'EDGE_RECOVERY_CONFIG_NOT_READY'}
    try:
        tenant, event = recipient_for_recovery(principal, cfg[1])
        bridge = edge or RecoveryEdgeClient(*cfg)
        receipt = bridge.exchange('inspect', tenant, event)
        if receipt is None:
            return {'status': 'NOT_STARTED', 'mode': MODE,
                    'real_garmin_activities_used': False,
                    'garmin_push_enabled': False, 'ai_data_sharing_enabled': False}
        checked = _check_receipt(receipt, tenant, event)
        return _safe_status(checked['acknowledged'], checked['attempts'])
    except RecoveryError:
        return {'status': 'EDGE_RECOVERY_STATUS_UNAVAILABLE'}
    except Exception:
        return {'status': 'EDGE_RECOVERY_STATUS_UNAVAILABLE'}


def _synthetic_neon_write(principal, user_id, event, store):
    owner = TrustedOwnerBinding(principal, user_id)
    body = json.dumps({'activities': [{
        'userId': user_id, 'summaryId': event, 'activityType': 'RUNNING',
        'startTimeInSeconds': FIXTURE_START, 'durationInSeconds': 1200,
        'distanceInMeters': 4000.0
    }]}).encode('utf-8')
    batch = prepare_for_owner(owner, parse_activity_push(body, 'application/json'))
    inbox = store or OfflinePostgresPushInbox()
    first = inbox.enqueue_offline_verified_fixture(owner, batch)
    second = inbox.enqueue_offline_verified_fixture(owner, batch)
    if ((first.enqueued, first.duplicates) not in ((1, 0), (0, 1)) or
            (second.enqueued, second.duplicates) != (0, 1)):
        raise PushStorageUnavailable('RECOVERY_INBOX_VERIFY_FAILED')
    return True


def rehearse_for_principal(principal, confirmation, scenario, *, env=None,
                            lookup=None, store=None, edge=None):
    if not isinstance(principal, VerifiedPrincipal):
        return {'status': 'NEON_AUTH_REQUIRED'}
    if confirmation != CONFIRM:
        return {'status': 'CONFIRMATION_REQUIRED', 'required': CONFIRM}
    if scenario not in SCENARIOS:
        return {'status': 'INVALID_SCENARIO', 'allowed_scenarios': sorted(SCENARIOS)}
    e = os.environ if env is None else env
    if e.get('GARMINAI_EDGE_RECOVERY_STAGING_ENABLED') != '1':
        return {'status': 'OPERATOR_DISABLED'}
    cfg = _bridge_config(e)
    if cfg is None:
        return {'status': 'EDGE_RECOVERY_CONFIG_NOT_READY'}
    try:
        user_id = (lookup or _linked_user_id)(principal)
        if not isinstance(user_id, str) or not user_id:
            return {'status': 'GARMIN_LINK_REQUIRED'}
        tenant, event = recipient_for_recovery(principal, cfg[1])
        bridge = edge or RecoveryEdgeClient(*cfg)
        receipt = _check_receipt(bridge.exchange('seed', tenant, event), tenant, event)
        if receipt['acknowledged'] and scenario != 'RECOVER':
            return {'status': 'SCENARIO_ALREADY_RECOVERED', 'd1_acknowledged': True}
        if scenario == 'SIMULATE_RENDER_DELAY':
            # No real Render downtime: D1 seed is durable; delayed pull is
            # represented by purposely skipping claim/Neon/ACK.
            return {'status': 'SIMULATED_RENDER_DELAY_D1_PENDING', 'retry_safe': True,
                    'neon_write_attempted': False, 'd1_acknowledged': False,
                    'real_garmin_activities_used': False}
        receipt = _check_receipt(bridge.exchange('claim', tenant, event), tenant, event)
        if scenario == 'SIMULATE_NEON_UNAVAILABLE':
            # No real outage is induced, no Neon write is attempted.
            return {'status': 'SIMULATED_NEON_UNAVAILABLE_D1_PENDING',
                    'retry_safe': True, 'neon_write_attempted': False,
                    'd1_acknowledged': False, 'real_garmin_activities_used': False}
        _synthetic_neon_write(principal, user_id, event, store)
        if scenario == 'SIMULATE_D1_ACK_UNAVAILABLE':
            # A controlled omission of ACK after a REAL synthetic Neon commit.
            return {'status': 'SIMULATED_D1_ACK_UNAVAILABLE_NEON_COMMITTED',
                    'retry_safe': True, 'neon_committed_or_existing': True,
                    'd1_acknowledged': False, 'real_garmin_activities_used': False}
        try:
            ack = _check_receipt(bridge.exchange('ack', tenant, event), tenant, event)
            if not ack['acknowledged']:
                raise RecoveryError('ACK_NOT_CONFIRMED')
        except RecoveryError:
            return {'status': 'NEON_COMMITTED_D1_ACK_PENDING',
                    'retry_safe': True, 'neon_committed_or_existing': True,
                    'real_garmin_activities_used': False}
        return {'status': 'PASS', 'mode': MODE, 'scenario': 'RECOVER',
                'neon_committed_or_existing': True,
                'neon_duplicate_prevented': True,
                'd1_acknowledged': True, 'd1_claim_attempts': ack['attempts'],
                'subject_scoped': True, 'synthetic_v118_limit_per_subject': 1,
                'real_garmin_activities_used': False,
                'garmin_push_enabled': False, 'ai_data_sharing_enabled': False}
    except RecoveryError:
        return {'status': 'EDGE_RECOVERY_NOT_READY', 'retry_safe': True}
    except (PushConflictingReplay, PushOwnershipRejected, PushStorageUnavailable,
            ValueError, PermissionError):
        return {'status': 'NEON_WRITE_NOT_CONFIRMED', 'retry_safe': True}
    except Exception:
        return {'status': 'RECOVERY_CHECK_NOT_READY', 'retry_safe': True}


def rehearse_from_context(ctx, confirmation, scenario):
    from .garmin_link_v101 import _principal_from_context
    return rehearse_for_principal(_principal_from_context(ctx), confirmation, scenario)


def status_from_context(ctx):
    from .garmin_link_v101 import _principal_from_context
    return status_for_principal(_principal_from_context(ctx))
