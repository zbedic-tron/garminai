import unittest
from garminai_public import core

class DemoTests(unittest.TestCase):
    def test_status(self):
        self.assertEqual(core.status()['mode'],'DEMO_ONLY')
    def test_list(self):
        self.assertEqual(core.activities(sport='running')['count'],4)
    def test_missing(self):
        self.assertEqual(core.detail('nope')['error'],'unknown_demo_activity')
    def test_weekly(self):
        self.assertGreater(sum(w['km'] for w in core.weekly_summary()['weeks'].values()),35)
    def test_invalid_dates(self):
        with self.assertRaises(ValueError):core.activities('2026-11-20','2026-11-01')
    def test_sources(self):
        self.assertGreaterEqual(core.literature()['count'],5)
        self.assertTrue(core.literature(topic='strength')['sources'])

if __name__=='__main__':unittest.main()
