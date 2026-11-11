"""Tenant-scoped PostgreSQL repository. NOT exposed via demo MCP endpoints.

Every operation requires a VerifiedPrincipal, and each query executes inside a
transaction with `SET LOCAL` equivalent via set_config. RLS + explicit subject
predicates provide two layers of isolation. Calls must never use arbitrary
user-supplied subject strings. No real users until identity provider is wired.
"""
from contextlib import contextmanager
import json
import os
from urllib.parse import urlsplit, parse_qs
from .identity import VerifiedPrincipal


def validate_database_url(url: str):
    if not isinstance(url,str) or not url or any(x in url for x in ('\n','\r')):
        raise ValueError('DATABASE_URL missing or invalid')
    parts=urlsplit(url)
    if parts.scheme not in ('postgres','postgresql') or not parts.hostname or not parts.username or not parts.password:
        raise ValueError('Expected a PostgreSQL URL with user, password and hostname')
    if parse_qs(parts.query).get('sslmode') not in (['require'],['verify-full']):
        raise ValueError('Database URL must require TLS')
    return url


def _subject(principal):
    if not isinstance(principal, VerifiedPrincipal):
        raise PermissionError('Verified identity required')
    return principal.subject


def _activity_id(activity_id):
    if not isinstance(activity_id,str) or not 1 <= len(activity_id) <= 128:
        raise ValueError('Invalid activity ID')
    return activity_id


class PostgresActivityStore:
    """Uses a short-lived connection per operation (Neon pooled URL is suitable).

    connection_factory is injectable for tests. The returned connection must
    support psycopg3 `with connection` transaction and cursor semantics.
    """
    def __init__(self, database_url=None, *, connection_factory=None):
        self.database_url=validate_database_url(database_url or os.environ.get('DATABASE_URL',''))
        self.connection_factory=connection_factory

    @contextmanager
    def _cursor(self, principal):
        subject=_subject(principal)
        if self.connection_factory is None:
            import psycopg
            conn=psycopg.connect(self.database_url, connect_timeout=8, autocommit=False)
        else:
            conn=self.connection_factory(self.database_url)
        # Connection context commits on success, rolls back on failure and closes.
        with conn:
            with conn.cursor() as cur:
                cur.execute("SELECT set_config('garminai.subject', %s, true)", (subject,))
                yield cur,subject

    def ensure_athlete(self, principal):
        with self._cursor(principal) as (cur,subject):
            cur.execute('INSERT INTO garminai.athletes(subject) VALUES (%s) ON CONFLICT DO NOTHING',(subject,))

    def upsert_activity(self, principal, activity_id, summary: dict, activity_date=None):
        aid=_activity_id(activity_id)
        if not isinstance(summary,dict):
            raise ValueError('Activity summary must be an object')
        payload=json.dumps(summary,ensure_ascii=False,allow_nan=False,separators=(',',':'))
        if len(payload.encode('utf-8'))>65536:
            raise ValueError('Activity summary too large')
        with self._cursor(principal) as (cur,subject):
            # Explicit tenant filter + DB RLS (must call ensure_athlete first).
            cur.execute("""INSERT INTO garminai.activities(subject,activity_id,activity_date,summary)
              VALUES (%s,%s,%s,%s::jsonb)
              ON CONFLICT(subject,activity_id) DO UPDATE SET
              activity_date=EXCLUDED.activity_date,summary=EXCLUDED.summary""",
              (subject,aid,activity_date,payload))

    def get_activity(self, principal, activity_id):
        aid=_activity_id(activity_id)
        with self._cursor(principal) as (cur,subject):
            cur.execute('SELECT summary FROM garminai.activities WHERE subject=%s AND activity_id=%s',(subject,aid))
            row=cur.fetchone()
            return row[0] if row else None

    def list_activities(self, principal, limit=50):
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError('Limit must be 1..100')
        with self._cursor(principal) as (cur,subject):
            cur.execute("""SELECT activity_id, activity_date, summary FROM garminai.activities
                         WHERE subject=%s ORDER BY activity_date DESC NULLS LAST, activity_id DESC LIMIT %s""",
                        (subject,limit))
            return [{'activity_id':r[0],'activity_date':r[1],'summary':r[2]} for r in cur.fetchall()]

    def delete_all(self, principal):
        with self._cursor(principal) as (cur,subject):
            # Cascades to activities, credentials and consent for this subject.
            cur.execute('DELETE FROM garminai.athletes WHERE subject=%s',(subject,))
            return cur.rowcount
