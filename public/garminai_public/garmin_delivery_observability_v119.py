"""v1.1.9 read-only synthetic observability + explicitly approved manual retry.

Uses the EXISTING, verified v1.1.8 D1 receipt. No new database, no
new Worker routes, no background runner, no real Garmin data or AI sharing.
Historical failure reasons and latency are not in the existing D1 schema;
never fabricate them. This is *not* production availability monitoring.
"""
from __future__ import annotations

import os

from .garmin_delivery_recovery_v118 import rehearse_for_principal, status_for_principal
from .identity import VerifiedPrincipal

CONFIRM = 'RUN_SYNTHETIC_SAFE_RETRY'
OPERATOR_FLAG = 'GARMINAI_EDGE_RELIABILITY_STAGING_ENABLED'
MAX_MANUAL_ATTEMPTS = 6
MODE = 'SYNTHETIC_RELIABILITY_READ_ONLY'


def _base(e):
    return {
        'mode': MODE,
        'manual_retry_enabled': e.get(OPERATOR_FLAG) == '1',
        'automatic_background_retry_enabled': False,
        'live_garmin_push_enabled': False,
        'real_garmin_activities_used': False,
        'ai_data_sharing_enabled': False,
        'production_readiness': 'BLOCKED',
        'last_failure_code': 'NOT_RECORDED_IN_V118_SCHEMA',
        'historical_latency_available': False,
        'neon_independently_queried': False,
    }


def _observe(principal, *, env=None, edge=None):
    e = os.environ if env is None else env
    base = _base(e)
    if not isinstance(principal, VerifiedPrincipal):
        return {**base, 'status': 'NEON_AUTH_REQUIRED', 'retry_permitted': False}
    detail = status_for_principal(principal, env=e, edge=edge)
    state = detail.get('status')
    if state == 'NOT_STARTED':
        return {**base, 'status': 'NOT_STARTED', 'delivery_state': 'NOT_STARTED',
                'd1_claim_attempts': 0, 'remaining_manual_attempts': MAX_MANUAL_ATTEMPTS,
                'd1_acknowledged': False, 'retry_permitted': False}
    if state not in ('ACKED_SYNTHETIC', 'PENDING_SYNTHETIC'):
        return {**base, 'status': 'OBSERVABILITY_UNAVAILABLE', 'retry_permitted': False}
    attempts = detail.get('d1_claim_attempts')
    acknowledged = detail.get('d1_acknowledged')
    if (type(attempts) is not int or not 0 <= attempts <= 1000000 or
            type(acknowledged) is not bool or
            acknowledged != (state == 'ACKED_SYNTHETIC')):
        return {**base, 'status': 'OBSERVABILITY_UNAVAILABLE', 'retry_permitted': False}
    remaining = max(0, MAX_MANUAL_ATTEMPTS - attempts)
    pending = state == 'PENDING_SYNTHETIC'
    retry_permitted = pending and remaining > 0 and e.get(OPERATOR_FLAG) == '1'
    return {**base,
            'status': 'OK',
            'delivery_state': state,
            'd1_acknowledged': acknowledged,
            'd1_claim_attempts': attempts,
            'remaining_manual_attempts': remaining,
            'retry_permitted': retry_permitted,
            'attention': ('NONE' if acknowledged else
                          'OPERATOR_ACTION_REQUIRED' if pending and remaining else
                          'MANUAL_ATTEMPT_LIMIT_REACHED'),
            'subject_scoped': True}


def observe_for_principal(principal, *, env=None, edge=None):
    """MCP-only read. No writes; never expose subject, token, event or payload."""
    try:
        return _observe(principal, env=env, edge=edge)
    except Exception:
        return {**_base(os.environ if env is None else env),
                'status': 'OBSERVABILITY_UNAVAILABLE', 'retry_permitted': False}


def manual_retry_for_principal(principal, confirmation, *, env=None, edge=None,
                               lookup=None, store=None):
    """One bounded operator-approved retry of an EXISTING pending v1.1.8 event.

    This is an application-side guard for a private manual lab, NOT an atomic
    D1 retry quota, lease, scheduler or multi-worker production guarantee.
    """
    e = os.environ if env is None else env
    if not isinstance(principal, VerifiedPrincipal):
        return {'status': 'NEON_AUTH_REQUIRED'}
    if confirmation != CONFIRM:
        return {'status': 'CONFIRMATION_REQUIRED', 'required': CONFIRM}
    if e.get(OPERATOR_FLAG) != '1':
        return {'status': 'OPERATOR_DISABLED'}
    try:
        before = _observe(principal, env=e, edge=edge)
        if before.get('status') != 'OK':
            return {'status': before['status'], 'retry_performed': False}
        if before['d1_acknowledged']:
            return {'status': 'ALREADY_ACKNOWLEDGED', 'retry_performed': False,
                    'd1_acknowledged': True}
        if before['remaining_manual_attempts'] == 0:
            return {'status': 'MANUAL_ATTEMPT_LIMIT_REACHED', 'retry_performed': False,
                    'd1_acknowledged': False}
        # The old scenario flag remains 0 in Render. Internally enable ONLY the
        # existing safe v1.1.8 RECOVER path after validating this new operator
        # permission and confirmation. Does not mutate process environment.
        recovery_env = dict(e, GARMINAI_EDGE_RECOVERY_STAGING_ENABLED='1')
        result = rehearse_for_principal(principal, 'RUN_SYNTHETIC_DELIVERY_RECOVERY',
                                       'RECOVER', env=recovery_env, edge=edge,
                                       lookup=lookup, store=store)
        if result.get('status') != 'PASS':
            return {'status': 'MANUAL_RETRY_NOT_CONFIRMED', 'retry_performed': True,
                    'retry_safe': True, 'd1_acknowledged': False,
                    'operator_review_required': True}
        after = _observe(principal, env=e, edge=edge)
        if after.get('status') != 'OK' or not after['d1_acknowledged']:
            return {'status': 'MANUAL_RETRY_ACK_NOT_CONFIRMED',
                    'retry_performed': True, 'retry_safe': True}
        return {'status': 'PASS', 'mode': MODE,
                'retry_performed': True, 'd1_acknowledged': True,
                'neon_duplicate_prevented': bool(result.get('neon_duplicate_prevented')),
                'd1_claim_attempts': after['d1_claim_attempts'],
                'subject_scoped': True, 'real_garmin_activities_used': False,
                'garmin_push_enabled': False, 'ai_data_sharing_enabled': False}
    except Exception:
        return {'status': 'MANUAL_RETRY_NOT_CONFIRMED', 'retry_performed': False,
                'retry_safe': True, 'operator_review_required': True}


def observe_from_context(ctx):
    from .garmin_link_v101 import _principal_from_context
    return observe_for_principal(_principal_from_context(ctx))


def manual_retry_from_context(ctx, confirmation):
    from .garmin_link_v101 import _principal_from_context
    return manual_retry_for_principal(_principal_from_context(ctx), confirmation)
