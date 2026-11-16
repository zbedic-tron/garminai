"""SQLite compatibility smoke test for the D1-only additive lab migration."""
from pathlib import Path
import sqlite3
import unittest

SCHEMA=Path(__file__).resolve().parents[1]/'edge_lab_v116'/'schema_recovery_v118.sql'
KEY='a'*64
EVENT='SYNTHETIC_RECOVERY_V118_'+'b'*32
DIGEST='c'*64


class RecoverySqliteSchemaTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(':memory:')
        self.db.executescript(SCHEMA.read_text())

    def tearDown(self):
        self.db.close()

    def test_idempotent_schema_and_one_row(self):
        self.db.executescript(SCHEMA.read_text())
        self.db.execute('INSERT INTO lab_recovery_v118(recipient_key,event_id,payload_digest) VALUES (?,?,?) ON CONFLICT(recipient_key,event_id) DO NOTHING',
                        (KEY,EVENT,DIGEST))
        self.db.execute('INSERT INTO lab_recovery_v118(recipient_key,event_id,payload_digest) VALUES (?,?,?) ON CONFLICT(recipient_key,event_id) DO NOTHING',
                        (KEY,EVENT,DIGEST))
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM lab_recovery_v118').fetchone()[0],1)

    def test_ack_persists_and_attempt_counter_only_changes_on_claim(self):
        self.db.execute('INSERT INTO lab_recovery_v118(recipient_key,event_id,payload_digest) VALUES (?,?,?)',
                        (KEY,EVENT,DIGEST))
        self.db.execute('UPDATE lab_recovery_v118 SET attempt_count=attempt_count+1 WHERE recipient_key=? AND event_id=? AND payload_digest=?',
                        (KEY,EVENT,DIGEST))
        self.db.execute('UPDATE lab_recovery_v118 SET acked_at=COALESCE(acked_at,CURRENT_TIMESTAMP) WHERE recipient_key=? AND event_id=? AND payload_digest=?',
                        (KEY,EVENT,DIGEST))
        saved=self.db.execute('SELECT attempt_count,acked_at FROM lab_recovery_v118').fetchone()
        self.assertEqual(saved[0],1)
        self.assertTrue(saved[1])
        self.db.execute('UPDATE lab_recovery_v118 SET acked_at=COALESCE(acked_at,CURRENT_TIMESTAMP) WHERE recipient_key=? AND event_id=? AND payload_digest=?',
                        (KEY,EVENT,DIGEST))
        self.assertEqual(self.db.execute('SELECT attempt_count,acked_at FROM lab_recovery_v118').fetchone(),saved)

    def test_wrong_or_non_synthetic_identifiers_rejected(self):
        for event,key,digest in [('REAL_GARMIN',KEY,DIGEST),
                                 (EVENT,'not-valid',DIGEST),
                                 (EVENT,KEY,'not-valid')]:
            with self.assertRaises(sqlite3.IntegrityError):
                self.db.execute('INSERT INTO lab_recovery_v118(recipient_key,event_id,payload_digest) VALUES (?,?,?)',
                                (key,event,digest))

if __name__=='__main__':unittest.main()
