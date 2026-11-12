import unittest
from garminai_public.db_check import check_database, startup_report, TABLES, POLICIES

URL = 'postgresql://garminai_app:fakepassword@example.test/neondb?sslmode=require'

class Cursor:
    def __init__(self, variant='ok'):
        self.variant = variant
        self.sql = []
        self.current = ''
    def __enter__(self): return self
    def __exit__(self, *_): return False
    def execute(self, sql):
        self.current = sql
        self.sql.append(sql)
        assert not any(word in sql.upper() for word in ('INSERT ', 'DELETE ', 'UPDATE ', 'CREATE ', 'ALTER ', 'DROP '))
    def fetchone(self):
        if 'current_user' in self.current and 'pg_roles' not in self.current:
            return ('neondb_owner' if self.variant == 'wrong-role' else 'garminai_app',)
        if 'pg_roles' in self.current:
            return (False, True, False, False) if self.variant == 'bypass' else (False, False, False, False)
        raise AssertionError('unexpected fetchone')
    def fetchall(self):
        if 'pg_class' in self.current:
            return [(t, True, False if self.variant == 'no-rls' and t == 'athletes' else True) for t in sorted(TABLES)]
        if 'pg_policies' in self.current:
            return [(p, 'ALL') for p in sorted(POLICIES)]
        if 'pg_tables' in self.current:
            return [(t, True) for t in sorted(TABLES)]
        raise AssertionError('unexpected fetchall')

class Connection:
    def __init__(self, variant): self.cur=Cursor(variant); self.closed=False
    def __enter__(self): return self
    def __exit__(self,*_): self.closed=True
    def cursor(self): return self.cur

class TestDBCheck(unittest.TestCase):
    def test_success_and_read_only(self):
        conn=Connection('ok')
        result=check_database(URL, connection_factory=lambda _:conn)
        self.assertTrue(result.ok)
        self.assertTrue(conn.closed)
        self.assertEqual(conn.cur.sql[0], 'SET TRANSACTION READ ONLY')
    def test_reject_wrong_role(self):
        self.assertEqual(check_database(URL, connection_factory=lambda _:Connection('wrong-role')).code,'WRONG_ROLE')
    def test_reject_bypassrls(self):
        self.assertEqual(check_database(URL, connection_factory=lambda _:Connection('bypass')).code,'PRIVILEGED_ROLE')
    def test_reject_disabled_force_rls(self):
        self.assertEqual(check_database(URL, connection_factory=lambda _:Connection('no-rls')).code,'RLS_DISABLED')
    def test_reject_invalid_url(self):
        self.assertEqual(check_database('postgresql://u:p@host/db').code,'INVALID_DATABASE_URL')
    def test_safe_report(self):
        printed=[]
        result=startup_report(URL,connection_factory=lambda _:Connection('ok'),printer=lambda msg,**_:printed.append(msg))
        self.assertEqual(printed,['GARMINAI_DB_CHECK: PASS (OK)'])
        self.assertNotIn('fakepassword',printed[0])
        self.assertTrue(result.ok)

if __name__=='__main__': unittest.main()
