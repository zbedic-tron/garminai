"""v1.1.0: durable Garmin activity-push *rehearsal* with a verified tenant.

CRITICAL: This is NOT wired to an HTTP handler, MCP tool, or background job.
The real sender-authentication mechanism has not yet been verified against
Garmin's partner documentation, so online push delivery MUST remain disabled.
Only the already bounded, token-stripped Activity summary projection can be
persisted, using an existing verified Neon principal + DB-linked Garmin user.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone

from .garmin_activity_staging import (PreparedStagingBatch, StagedActivity,
                                      TrustedOwnerBinding, prepare_for_owner)
from .postgres_store import validate_database_url


class PushStorageUnavailable(RuntimeError):
    """Do not reveal database errors to public callers."""


class PushOwnershipRejected(PermissionError):
    pass


class PushConflictingReplay(ValueError):
    pass


@dataclass(frozen=True)
class RehearsalResult:
    inserted: int
    duplicate: int


def normalized_summary(activity: StagedActivity) -> dict:
    """Allowlisted JSON projection. NO Garmin userId, tokens, FIT, GPS or HR."""
    if not isinstance(activity, StagedActivity):
        raise ValueError('Untrusted activity type')
    return {
        'source': 'garmin_activity_summary_staged',
        'activity_type': activity.activity_type,
        'start_time_seconds': activity.start_time_seconds,
        'duration_seconds': activity.duration_seconds,
        'distance_meters': activity.distance_meters,
    }


def _serialized(obj: dict) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False)


def _digest(subject: str, activity_id: str, serialized: str) -> str:
    return hashlib.sha256((subject + '\0' + activity_id + '\0' + serialized).encode()).hexdigest()


def _assert_batch(binding: TrustedOwnerBinding, batch: PreparedStagingBatch):
    if not isinstance(binding, TrustedOwnerBinding) or not isinstance(batch, PreparedStagingBatch):
        raise PushOwnershipRejected('VERIFIED_LINK_AND_BATCH_REQUIRED')
    if not batch.events or batch.subject != binding.principal.subject:
        raise PushOwnershipRejected('SUBJECT_MISMATCH')
    # Recalculate instead of trusting any caller-constructed PreparedStagingBatch.
    expected = prepare_for_owner(binding, batch.events)
    if expected != batch:
        raise PushOwnershipRejected('BATCH_INTEGRITY_INVALID')


class PostgresPushRehearsalStore:
    """Short tenant-local PostgreSQL transaction with durable idempotency.

    This class intentionally requires the caller to provide TrustedOwnerBinding.
    Only use in OFFLINE tests until authenticated Garmin notification delivery
    and ownership mapping have been reviewed. It is never called from HTTP.
    """
    def __init__(self, database_url=None, *, connection_factory=None):
        self.database_url = validate_database_url(database_url or os.environ.get('DATABASE_URL', ''))
        self.connection_factory = connection_factory

    def persist_offline_verified_fixture(self, binding: TrustedOwnerBinding,
                                         batch: PreparedStagingBatch) -> RehearsalResult:
        _assert_batch(binding, batch)
        if self.connection_factory is None:
            import psycopg
            connection_factory = lambda url: psycopg.connect(url, connect_timeout=8, autocommit=False)
        else:
            connection_factory = self.connection_factory
        inserted = 0
        duplicate = batch.duplicate_count
        # Transaction context commits only on full success; any exception rolls
        # back activities and receipts together. DO NOT turn this into a webhook.
        with connection_factory(self.database_url) as conn:
            with conn.cursor() as cur:
                cur.execute('SELECT current_user')
                if cur.fetchone()[0] != 'garminai_app':
                    raise PushStorageUnavailable('WRONG_DATABASE_ROLE')
                cur.execute("SELECT set_config('garminai.subject', %s, true)", (binding.principal.subject,))
                cur.execute("""SELECT c.relname,c.relrowsecurity,c.relforcerowsecurity
                  FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                  WHERE n.nspname='garminai' AND c.relname IN ('athletes','activities','garmin_credentials','garmin_push_receipts')""")
                flags = {row[0]:(row[1],row[2]) for row in cur.fetchall()}
                if set(flags) != {'athletes','activities','garmin_credentials','garmin_push_receipts'} or any(
                        not a or not b for a,b in flags.values()):
                    raise PushStorageUnavailable('PUSH_SCHEMA_OR_RLS_NOT_READY')
                cur.execute('SELECT garmin_user_id FROM garminai.athletes WHERE subject=%s FOR UPDATE',
                            (binding.principal.subject,))
                row = cur.fetchone()
                if not row or not isinstance(row[0],str) or not hmac.compare_digest(
                        row[0], binding.linked_garmin_user_id):
                    raise PushOwnershipRejected('GARMIN_LINK_NOT_VERIFIED')
                cur.execute('SELECT 1 FROM garminai.garmin_credentials WHERE subject=%s',
                            (binding.principal.subject,))
                if cur.fetchone() is None:
                    raise PushOwnershipRejected('GARMIN_LINK_NOT_VERIFIED')
                for activity in batch.events:
                    summary = normalized_summary(activity)
                    payload = _serialized(summary)
                    digest = _digest(binding.principal.subject, activity.activity_id, payload)
                    event_date = datetime.fromtimestamp(activity.start_time_seconds, tz=timezone.utc)
                    cur.execute("""INSERT INTO garminai.activities(subject,activity_id,activity_date,summary)
                        VALUES (%s,%s,%s,%s::jsonb) ON CONFLICT(subject,activity_id) DO NOTHING
                        RETURNING activity_id""",
                        (binding.principal.subject, activity.activity_id, event_date, payload))
                    was_inserted = cur.fetchone() is not None
                    if not was_inserted:
                        cur.execute('SELECT summary FROM garminai.activities WHERE subject=%s AND activity_id=%s FOR UPDATE',
                                    (binding.principal.subject, activity.activity_id))
                        existing = cur.fetchone()
                        if existing is None:
                            raise PushStorageUnavailable('RETRY_TRANSACTION_REQUIRED')
                        stored = existing[0]
                        if isinstance(stored,str):
                            stored = json.loads(stored)
                        if _serialized(stored) != payload:
                            raise PushConflictingReplay('CONFLICTING_ACTIVITY_SUMMARY')
                    cur.execute("""INSERT INTO garminai.garmin_push_receipts(subject,activity_id,payload_sha256)
                        VALUES (%s,%s,%s) ON CONFLICT(subject,activity_id) DO NOTHING
                        RETURNING payload_sha256""",
                        (binding.principal.subject, activity.activity_id, digest))
                    receipt_was_inserted = cur.fetchone() is not None
                    if not receipt_was_inserted:
                        cur.execute('SELECT payload_sha256 FROM garminai.garmin_push_receipts WHERE subject=%s AND activity_id=%s',
                                    (binding.principal.subject, activity.activity_id))
                        prior = cur.fetchone()
                        if prior is None or not hmac.compare_digest(str(prior[0]),digest):
                            raise PushConflictingReplay('CONFLICTING_ACTIVITY_RECEIPT')
                    if was_inserted and receipt_was_inserted:
                        inserted += 1
                    else:
                        duplicate += 1
        return RehearsalResult(inserted, duplicate)
