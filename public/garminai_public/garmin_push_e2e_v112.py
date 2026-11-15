"""v1.1.2 — opt-in, subject-scoped synthetic-only PostgreSQL rehearsal.

NOT an HTTP webhook; NOT an authentic Garmin notification; NOT a real-data MCP
reader. A confirmed call adds at most one marked fictional row per verified
Neon subject to the offline inbox, then repeats the identical write to prove
transactional deduplication. This does not validate a live Garmin ingress path.
"""
from __future__ import annotations

import json
import os

from .garmin_activity_staging import TrustedOwnerBinding, parse_activity_push, prepare_for_owner
from .garmin_push_inbox_v111 import OfflinePostgresPushInbox
from .garmin_push_rehearsal_v110 import (PushConflictingReplay, PushOwnershipRejected,
                                         PushStorageUnavailable)
from .identity import VerifiedPrincipal

CONFIRM = 'RUN_SYNTHETIC_REHEARSAL'
FIXTURE_ID = 'GARMINAI_SYNTHETIC_V112'  # reserved and never processed as a real activity
FIXTURE_START = 1794650000  # arbitrary fictional date, not a real workout


def _linked_user_id(principal: VerifiedPrincipal) -> str | None:
    """Read only the user's linked Garmin identifier, through RLS, never token data."""
    from .garmin_link_v101 import _db_cursor
    with _db_cursor(principal) as cur:
        cur.execute('''SELECT a.garmin_user_id FROM garminai.athletes a
            JOIN garminai.garmin_credentials c ON c.subject = a.subject
            WHERE a.subject=%s''', (principal.subject,))
        row = cur.fetchone()
    return row[0] if row else None


def rehearse_for_verified_principal(principal, confirmation, *, env=None,
                                     lookup=None, store=None) -> dict:
    """For private MCP use only. Safe, fixed-shape output; no IDs or secrets.

    `lookup` and `store` injection is ONLY for deterministic synthetic tests.
    A real call always resolves ownership from a verified Neon principal and
    existing RLS-linked DB state. The operator must opt in via Render env.
    """
    if not isinstance(principal, VerifiedPrincipal):
        return {'status': 'NEON_AUTH_REQUIRED'}
    if confirmation != CONFIRM:
        return {'status': 'CONFIRMATION_REQUIRED', 'required': CONFIRM,
                'effect': 'At most one persistent fictional inbox row for the authenticated account.'}
    e = os.environ if env is None else env
    if e.get('GARMINAI_PUSH_REHEARSAL_STAGING_ENABLED') != '1':
        return {'status': 'OPERATOR_DISABLED',
                'message': 'Operator has not enabled the synthetic database rehearsal.'}
    # The only allowed object written has fixed synthetic fields and never
    # contains Garmin-sourced workout data, token material, or a real activity ID.
    try:
        user_id = (lookup or _linked_user_id)(principal)
        if not isinstance(user_id, str) or not user_id:
            return {'status': 'GARMIN_LINK_REQUIRED'}
        binding = TrustedOwnerBinding(principal, user_id)
        raw = json.dumps({'activities': [{
            'userId': user_id,
            'summaryId': FIXTURE_ID,
            'activityType': 'RUNNING',
            'startTimeInSeconds': FIXTURE_START,
            'durationInSeconds': 1200,
            'distanceInMeters': 4000.0,
        }]}).encode('utf-8')
        batch = prepare_for_owner(binding, parse_activity_push(raw, 'application/json'))
        inbox = store or OfflinePostgresPushInbox()
        first = inbox.enqueue_offline_verified_fixture(binding, batch)
        second = inbox.enqueue_offline_verified_fixture(binding, batch)
        # Existing data must never silently be overwritten, and one duplicate
        # must never be counted as a newly inserted record.
        if (first.enqueued, first.duplicates) not in ((1, 0), (0, 1)) or \
                (second.enqueued, second.duplicates) != (0, 1):
            return {'status': 'CHECK_FAILED'}
        return {'status': 'PASS', 'fixture': 'SYNTHETIC_ONLY',
                'committed_first_or_existing': True, 'duplicate_prevented': True,
                'scoped_by_verified_neon_subject': True,
                'real_activities_read': False, 'garmin_push_enabled': False,
                'ai_sharing_enabled': False,
                'persistent_fixture_limit_per_subject': 1}
    except (PushConflictingReplay, PushOwnershipRejected, PushStorageUnavailable,
            ValueError, PermissionError):
        return {'status': 'CHECK_FAILED'}
    except Exception:
        # Never expose database errors, user IDs, hostnames, tokens or credentials.
        return {'status': 'STORAGE_NOT_READY'}


def rehearse_from_context(ctx, confirmation) -> dict:
    from .garmin_link_v101 import _principal_from_context
    return rehearse_for_verified_principal(_principal_from_context(ctx), confirmation)
