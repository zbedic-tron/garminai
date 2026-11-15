"""Garmin Activity API *push* parser and identity-scoped offline rehearsal.

SAFETY BOUNDARY: this module is not reachable through any public write route.
Garmin push sender-authentication is not yet verified against the private
Garmin Activity API contract. Do not treat an HTTPS request or a `userId`
field as proof that Garmin sent it. Do not persist real data using this code.

Only the `activities` (JSON summary) shape is rehearsed. Other Garmin push
families require exact partner documentation before enabling live ingestion.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import math
import re
from dataclasses import dataclass

from .garmin_push import MAX_PUSH_BYTES
from .identity import VerifiedPrincipal

MAX_ACTIVITIES_PER_PUSH = 100
_ID_RE = re.compile(r'^[A-Za-z0-9._:-]{1,128}$')
_KIND_RE = re.compile(r'^[A-Za-z0-9_:-]{1,64}$')


class UntrustedNotification(ValueError):
    """Unverified or unexpected push content; never expose internals to clients."""


def _unique_keys(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise UntrustedNotification('duplicate JSON key')
        obj[key] = value
    return obj


def _no_non_finite(_):
    raise UntrustedNotification('non-finite JSON value')


def _uid(value):
    return isinstance(value, str) and bool(_ID_RE.fullmatch(value))


def _bounded_number(value, *, minimum=0, maximum=1e9):
    return (type(value) in (int, float) and math.isfinite(value)
            and minimum <= value <= maximum)


@dataclass(frozen=True)
class StagedActivity:
    """A bounded, allowlisted subset of a FICTIONAL or untrusted summary."""
    garmin_user_id: str
    activity_id: str
    activity_type: str
    start_time_seconds: int
    duration_seconds: float
    distance_meters: float | None


@dataclass(frozen=True)
class TrustedOwnerBinding:
    """Must come from server-side verified identity + DB-linked Garmin account.

    Never instantiate using userId from a push, a browser header, or an MCP
    tool argument. In v1.0 this is exercised ONLY in offline unit tests.
    """
    principal: VerifiedPrincipal
    linked_garmin_user_id: str

    def __post_init__(self):
        if not isinstance(self.principal, VerifiedPrincipal) or not _uid(self.linked_garmin_user_id):
            raise PermissionError('verified identity and server-side link required')


@dataclass(frozen=True)
class PreparedStagingBatch:
    subject: str
    events: tuple[StagedActivity, ...]
    event_fingerprints: tuple[str, ...]
    duplicate_count: int


def parse_activity_push(raw: bytes, content_type: str) -> tuple[StagedActivity, ...]:
    """Parse a constrained example Activity summary push, no side effects.

    Unknown fields (including userAccessToken) are discarded; the full body
    is not written to files, logs, or any database. Empty pushes are rejected.
    """
    if (not isinstance(raw, bytes) or not 1 <= len(raw) <= MAX_PUSH_BYTES or
            not isinstance(content_type, str) or
            content_type.split(';', 1)[0].strip().lower() != 'application/json'):
        raise UntrustedNotification('invalid content type or size')
    try:
        obj = json.loads(raw.decode('utf-8'), object_pairs_hook=_unique_keys,
                         parse_constant=_no_non_finite)
    except (UnicodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
        raise UntrustedNotification('invalid JSON') from exc
    # Do not accidentally accept other, unreviewed push families.
    if not isinstance(obj, dict) or set(obj) != {'activities'}:
        raise UntrustedNotification('unexpected summary type')
    summaries = obj['activities']
    if not isinstance(summaries, list) or not 1 <= len(summaries) <= MAX_ACTIVITIES_PER_PUSH:
        raise UntrustedNotification('invalid activity count')
    result = []
    for summary in summaries:
        if not isinstance(summary, dict):
            raise UntrustedNotification('invalid summary')
        uid, aid, kind = (summary.get('userId'), summary.get('summaryId'),
                          summary.get('activityType'))
        start = summary.get('startTimeInSeconds')
        duration = summary.get('durationInSeconds')
        distance = summary.get('distanceInMeters')
        if (not _uid(uid) or not _uid(aid) or
                not isinstance(kind, str) or not _KIND_RE.fullmatch(kind) or
                type(start) is not int or not 0 <= start <= 4102444800 or
                not _bounded_number(duration, maximum=2592000) or
                (distance is not None and not _bounded_number(distance, maximum=5000000))):
            raise UntrustedNotification('invalid activity fields')
        result.append(StagedActivity(uid, aid, kind, start,
                                     float(duration), None if distance is None else float(distance)))
    return tuple(result)


def prepare_for_owner(binding: TrustedOwnerBinding, items: tuple[StagedActivity, ...]):
    """Prepare fictional samples for an ALREADY LINKED principal, never a write.

    Reject the *whole* push if even one record references a different Garmin
    user. Per-owner/per-activity deterministic digests help rehearse de-duping.
    """
    if not isinstance(binding, TrustedOwnerBinding) or not isinstance(items, tuple) or not items:
        raise PermissionError('verified owner and nonempty payload required')
    if any(not isinstance(a, StagedActivity) or
           not hmac.compare_digest(a.garmin_user_id, binding.linked_garmin_user_id)
           for a in items):
        raise PermissionError('cross-account activity push refused')
    distinct, hashes = {}, []
    duplicate_count = 0
    for item in items:
        # No raw user access tokens in the projected data or fingerprints.
        event_key = f'{binding.principal.subject}\x00{item.activity_id}'
        digest = hashlib.sha256(event_key.encode('utf-8')).hexdigest()
        if digest in distinct:
            duplicate_count += 1
            if distinct[digest] != item:
                raise UntrustedNotification('conflicting duplicate activity')
            continue
        distinct[digest] = item
        hashes.append(digest)
    return PreparedStagingBatch(binding.principal.subject, tuple(distinct.values()),
                                tuple(hashes), duplicate_count)


def integration_status(env=None):
    """Public-safe state: no credential presence, identifiers, or secrets."""
    from .garmin_link_v101 import configuration as link_config
    link = link_config(env)
    return {
        'version':'1.1.4', 'phase':'PUSH_INGRESS_OPERATIONAL_READINESS_OFFLINE',
        'garmin_starter_delivery':'PUSH_ONLY',
        'oauth_connect_enabled':link['enabled'],
        'oauth_link_requested':link['requested'],
        'oauth_link_config_issues':link['issues'],
        'push_ingestion_enabled':False,
        'real_garmin_data_stored':False,
        'mcp_real_garmin_data_enabled':False,
        'parser_offline_rehearsal':'activities_summary_only',
        'durable_offline_rehearsal_ready_after_migration':True,
        'offline_durable_inbox_requires_migration_005': True,
        'synthetic_rehearsal_operator_enabled':(
            (__import__('os').environ if env is None else env).get('GARMINAI_PUSH_REHEARSAL_STAGING_ENABLED') == '1'),
        'render_source_ip_trust_verified': False,
        'verified_live_ingress_enabled': False,
        'garmin_sender_authentication_verified':False,
        'blocked_until':[
            'official_push_sender_authentication_verified',
            'verified_neon_subject_to_garmin_user_link',
            'encrypted_garmin_token_lifecycle_and_consent',
            'replay_safe_durable_ingestion_and_deletion',
            'garmin_terms_and_ai_data_sharing_review',
        ],
        'next':'Synthetic Neon PASS has been reported; Garmin live ingress remains blocked by sender provenance and Free-host cold-start risks. Keep all Garmin push endpoints disabled.',
    }
