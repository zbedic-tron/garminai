import unittest
from test_db_check_v061 import URL, Connection, Cursor
from garminai_public.db_check import check_database

class MigratedCursor(Cursor):
    def fetchall(self):
        if 'pg_class' in self.current:
            return [('activities', True, True),('athletes', True, True),('ai_consent', True, True),('garmin_credentials', True, True),('oauth_attempts', True, True)]
        if 'pg_policies' in self.current:
            return [('activities_owner','ALL'),('athletes_owner','ALL'),('consent_owner','ALL'),('credentials_owner','ALL'),('oauth_attempts_owner','ALL')]
        if 'pg_tables' in self.current:
            return [(n, True) for n in ('activities','athletes','ai_consent','garmin_credentials','oauth_attempts')]
        return super().fetchall()

class MigratedConnection(Connection):
    def __init__(self): self.cur=MigratedCursor('ok'); self.closed=False

class TestOptionalMigration(unittest.TestCase):
    def test_checker_accepts_migrated_schema(self):
        self.assertTrue(check_database(URL,connection_factory=lambda _:MigratedConnection()).ok)

if __name__=='__main__': unittest.main()
