import base64
import secrets
import unittest
from pathlib import Path
from cryptography.exceptions import InvalidTag
from garminai_public.identity import DemoIdentityVerifier
from garminai_public.postgres_store import PostgresActivityStore, validate_database_url
from garminai_public.token_vault import TokenVault, load_key
from garminai_public.db_readiness import db_configuration_status


class _Cursor:
    def __init__(self, owner): self.owner=owner
    def __enter__(self): return self
    def __exit__(self,*_):pass
    def execute(self,query,params):
        self.owner.queries.append((query,params))
        if 'set_config' in query: self.owner.subject=params[0]
    def fetchone(self): return None
    def fetchall(self): return []

class _Connection:
    def __init__(self):self.queries=[];self.subject=None;self.closed=False
    def __enter__(self):return self
    def __exit__(self,*_):self.closed=True
    def cursor(self):return _Cursor(self)

class TestPostgresV06(unittest.TestCase):
    def setUp(self):
        signer=DemoIdentityVerifier(b'z'*32)
        self.a=signer.verify(signer.issue_for_test('runner-A'))
        self.b=signer.verify(signer.issue_for_test('runner-B'))
        self.connections=[]
        def factory(_url):
            conn=_Connection();self.connections.append(conn);return conn
        self.repo=PostgresActivityStore('postgresql://runtime:secret@db.neon.tech/neondb?sslmode=require',connection_factory=factory)

    def test_db_fails_without_tls(self):
        with self.assertRaises(ValueError): validate_database_url('postgresql://u:p@host/db')
        with self.assertRaises(ValueError): validate_database_url('postgresql://u:p@host/db?sslmode=disable')

    def test_verified_principal_required(self):
        with self.assertRaises(PermissionError): self.repo.get_activity('runner-A','run1')
        self.assertEqual(len(self.connections),0)

    def test_scope_reset_each_transaction(self):
        self.repo.get_activity(self.a,'run1')
        self.repo.get_activity(self.b,'run1')
        self.assertEqual([c.subject for c in self.connections],['runner-A','runner-B'])
        for conn in self.connections:
            self.assertTrue(conn.closed)
            self.assertIn("set_config('garminai.subject'",conn.queries[0][0])
            self.assertEqual(conn.queries[0][1],(conn.subject,))
            self.assertIn('subject=%s',conn.queries[1][0])
            self.assertEqual(conn.queries[1][1][0],conn.subject)

    def test_activity_id_rejects_invalid(self):
        for id in ('',None,'a'*129):
            with self.assertRaises(ValueError): self.repo.get_activity(self.a,id)

    def test_summary_limits_and_sql_parameterization(self):
        self.repo.upsert_activity(self.a,'a1',{'km':10})
        q,p=self.connections[-1].queries[1]
        self.assertIn('%s::jsonb',q)
        self.assertEqual(p[0:2],('runner-A','a1'))
        with self.assertRaises(ValueError):self.repo.upsert_activity(self.a,'bad',{'x':'a'*70000})
        self.assertEqual(len(self.connections),1)

    def test_no_user_input_in_readiness(self):
        status=db_configuration_status({'DATABASE_URL':'postgresql://u:pw@host/db?sslmode=require'})
        self.assertTrue(status['postgres_url_configured_and_tls_required'])
        self.assertNotIn('pw',str(status))
        self.assertFalse(status['real_garmin_data_enabled'])

    def test_aes_gcm_is_bound_to_user(self):
        key=secrets.token_bytes(32)
        box=TokenVault(key)
        nonce,blob=box.seal(self.a,b'{"refresh_token":"private"}')
        self.assertNotIn(b'private',blob)
        self.assertEqual(box.open(self.a,nonce,blob),b'{"refresh_token":"private"}')
        with self.assertRaises(InvalidTag): box.open(self.b,nonce,blob)
        with self.assertRaises(PermissionError): box.seal('runner-A',b'no')
        self.assertEqual(load_key(base64.urlsafe_b64encode(key).decode()),key)

    def test_rls_schema_has_force_policies(self):
        sql=(Path(__file__).parents[1]/'sql/001_init.sql').read_text()
        for table in ('athletes','activities','garmin_credentials','ai_consent'):
            self.assertIn('ALTER TABLE garminai.'+table+' FORCE ROW LEVEL SECURITY',sql)
            self.assertIn('ALTER TABLE garminai.'+table+' ENABLE ROW LEVEL SECURITY',sql)
        self.assertEqual(sql.count("nullif(current_setting('garminai.subject', true), '')"),8)
