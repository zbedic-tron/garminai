"""v1.1.1 OFFLINE Garmin push durable inbox rehearsal.

NEVER called from an HTTP handler; this is not a Garmin sender authenticator.
Only synthetic, allowlisted Activity summaries are handled. Sender IPs and
real Garmin payloads must NOT be routed here until ingress provenance and
Garmin license restrictions are independently verified.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
from dataclasses import dataclass

from .garmin_activity_staging import PreparedStagingBatch, TrustedOwnerBinding
from .garmin_push_rehearsal_v110 import (
    PushConflictingReplay, PushOwnershipRejected, PushStorageUnavailable,
    _assert_batch, normalized_summary, _serialized,
)
from .postgres_store import validate_database_url


@dataclass(frozen=True)
class OfflineInboxResult:
    enqueued: int
    duplicates: int


def _summary_hash(subject: str, activity_id: str, serialized: str) -> str:
    return hashlib.sha256((subject + '\x00' + activity_id + '\x00' + serialized).encode()).hexdigest()


class OfflinePostgresPushInbox:
    """Durably enqueue synthetic summaries, without processing activities.

    Database transaction must commit BEFORE any future HTTP 200. The real
    network-facing route remains intentionally disabled in this release.
    """

    def __init__(self, database_url=None, *, connection_factory=None):
        self.database_url = validate_database_url(database_url or os.environ.get('DATABASE_URL', ''))
        self.connection_factory = connection_factory

    def enqueue_offline_verified_fixture(self, binding: TrustedOwnerBinding,
                                         batch: PreparedStagingBatch) -> OfflineInboxResult:
        _assert_batch(binding, batch)
        if self.connection_factory is None:
            import psycopg
            connection_factory = lambda url: psycopg.connect(url, connect_timeout=8, autocommit=False)
        else:
            connection_factory = self.connection_factory
        enqueued = 0
        duplicates = batch.duplicate_count
        # A failed statement rolls back ALL enqueued events in the batch.
        with connection_factory(self.database_url) as conn:
            with conn.cursor() as cur:
                cur.execute('SELECT current_user')
                if cur.fetchone()[0] != 'garminai_app':
                    raise PushStorageUnavailable('WRONG_DATABASE_ROLE')
                cur.execute("SELECT set_config('garminai.subject', %s, true)", (binding.principal.subject,))
                cur.execute("""SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity
                    FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
                    WHERE n.nspname='garminai' AND c.relname IN
                    ('athletes','garmin_credentials','garmin_push_inbox')""")
                rows = {name: (rls, forced) for name, rls, forced in cur.fetchall()}
                if set(rows) != {'athletes','garmin_credentials','garmin_push_inbox'} or not all(
                        rls and forced for rls, forced in rows.values()):
                    raise PushStorageUnavailable('INBOX_SCHEMA_OR_RLS_NOT_READY')
                cur.execute('SELECT garmin_user_id FROM garminai.athletes WHERE subject=%s FOR UPDATE',
                            (binding.principal.subject,))
                owner = cur.fetchone()
                if not owner or not isinstance(owner[0], str) or not hmac.compare_digest(
                        owner[0], binding.linked_garmin_user_id):
                    raise PushOwnershipRejected('GARMIN_LINK_NOT_VERIFIED')
                cur.execute('SELECT 1 FROM garminai.garmin_credentials WHERE subject=%s',
                            (binding.principal.subject,))
                if cur.fetchone() is None:
                    raise PushOwnershipRejected('GARMIN_LINK_NOT_VERIFIED')
                for activity in batch.events:
                    payload = _serialized(normalized_summary(activity))
                    digest = _summary_hash(binding.principal.subject, activity.activity_id, payload)
                    cur.execute("""INSERT INTO garminai.garmin_push_inbox
                        (subject,activity_id,payload_sha256,summary)
                        VALUES (%s,%s,%s,%s::jsonb)
                        ON CONFLICT(subject,activity_id) DO NOTHING
                        RETURNING payload_sha256""",
                        (binding.principal.subject, activity.activity_id, digest, payload))
                    if cur.fetchone() is not None:
                        enqueued += 1
                        continue
                    cur.execute("""SELECT payload_sha256,summary FROM garminai.garmin_push_inbox
                        WHERE subject=%s AND activity_id=%s FOR UPDATE""",
                        (binding.principal.subject, activity.activity_id))
                    old = cur.fetchone()
                    if old is None:
                        raise PushStorageUnavailable('INBOX_RETRY_REQUIRED')
                    saved_summary = json.loads(old[1]) if isinstance(old[1], str) else old[1]
                    if not hmac.compare_digest(str(old[0]), digest) or _serialized(saved_summary) != payload:
                        raise PushConflictingReplay('CONFLICTING_INBOX_EVENT')
                    duplicates += 1
        return OfflineInboxResult(enqueued, duplicates)
