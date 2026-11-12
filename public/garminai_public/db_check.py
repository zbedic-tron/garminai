"""One-time, read-only Neon PostgreSQL connectivity/schema check.

Not an authentication system or a production readiness guarantee.
Never log database URLs, credentials, SQL error messages, or user rows.
"""
import os
from dataclasses import dataclass
from .postgres_store import validate_database_url

TABLES = frozenset({'athletes', 'activities', 'garmin_credentials', 'ai_consent'})
POLICIES = frozenset({'athletes_owner', 'activities_owner', 'credentials_owner', 'consent_owner'})
OPTIONAL_TABLES = frozenset({'oauth_attempts'})
OPTIONAL_POLICIES = frozenset({'oauth_attempts_owner'})

@dataclass(frozen=True)
class CheckResult:
    ok: bool
    code: str
    # Fixed, non-sensitive messages. Avoid exception str() and DB hostnames.


def check_database(database_url=None, *, connection_factory=None):
    """Check a read-only connection as non-privileged garminai_app.

    No CREATE/INSERT/UPDATE/DELETE, no external user data accessed.
    Every check runs inside a transaction with read-only semantics.
    """
    url = database_url if database_url is not None else os.environ.get('DATABASE_URL', '')
    try:
        validate_database_url(url)
    except ValueError:
        return CheckResult(False, 'INVALID_DATABASE_URL')

    try:
        if connection_factory is None:
            import psycopg
            connection_factory = lambda u: psycopg.connect(u, connect_timeout=8)
        with connection_factory(url) as conn:
            with conn.cursor() as cur:
                cur.execute('SET TRANSACTION READ ONLY')
                cur.execute('SELECT current_user')
                role = cur.fetchone()[0]
                if role != 'garminai_app':
                    return CheckResult(False, 'WRONG_ROLE')
                cur.execute('''SELECT rolsuper, rolbypassrls, rolcreaterole, rolcreatedb
                               FROM pg_roles WHERE rolname = current_user''')
                attrs = cur.fetchone()
                if attrs is None or any(attrs):
                    return CheckResult(False, 'PRIVILEGED_ROLE')
                cur.execute('''SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity
                               FROM pg_class c
                               JOIN pg_namespace n ON n.oid = c.relnamespace
                               WHERE n.nspname = 'garminai' AND c.relkind = 'r' ''')
                rows = cur.fetchall()
                if not TABLES.issubset({r[0] for r in rows}) or not {r[0] for r in rows}.issubset(TABLES | OPTIONAL_TABLES):
                    return CheckResult(False, 'SCHEMA_MISMATCH')
                if any(not r[1] or not r[2] for r in rows):
                    return CheckResult(False, 'RLS_DISABLED')
                cur.execute('''SELECT policyname, cmd FROM pg_policies
                               WHERE schemaname = 'garminai' ''')
                policies = cur.fetchall()
                if not (POLICIES | (OPTIONAL_POLICIES if 'oauth_attempts' in {r[0] for r in rows} else set())).issubset({r[0] for r in policies}) or any(
                    cmd != 'ALL' for name, cmd in policies if name in POLICIES
                ):
                    return CheckResult(False, 'POLICY_MISMATCH')
                cur.execute('''SELECT tablename,
                         has_table_privilege(current_user, format('garminai.%I', tablename), 'SELECT')
                         FROM pg_tables WHERE schemaname = 'garminai' ''')
                privs = cur.fetchall()
                if {t for t,_ in privs} != {r[0] for r in rows} or any(not granted for _, granted in privs):
                    return CheckResult(False, 'MISSING_PRIVILEGES')
        return CheckResult(True, 'OK')
    except Exception:
        # Intentionally do not leak exception messages into logs/UI; these may
        # contain fragments of connection strings or internal infrastructure.
        return CheckResult(False, 'CONNECTION_OR_QUERY_FAILED')


def startup_report(database_url=None, *, connection_factory=None, printer=print):
    result = check_database(database_url, connection_factory=connection_factory)
    printer('GARMINAI_DB_CHECK: ' + ('PASS' if result.ok else 'FAIL') + ' (' + result.code + ')', flush=True)
    return result
