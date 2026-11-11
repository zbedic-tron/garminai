import json
import unittest
from pathlib import Path
from garminai_public import core

ROOT = Path(__file__).resolve().parents[2]
PUBLIC = ROOT / 'public'

class DeploymentFiles(unittest.TestCase):
    def test_blueprint_present(self):
        config=(ROOT/'render.yaml').read_text(encoding='utf-8')
        self.assertIn('rootDir: public',config)
        self.assertIn('healthCheckPath: /healthz',config)
        self.assertIn('garminai_public.http_server:app',config)
    def test_demo_only_and_no_secrets(self):
        self.assertEqual(core.status()['mode'],'DEMO_ONLY')
        self.assertEqual(core.status()['garmin_oauth'],'NOT_CONNECTED')
    def test_bibliography_present(self):
        self.assertGreaterEqual(len(json.loads((PUBLIC/'data/literature/approved.json').read_text(encoding='utf-8'))['sources']),5)
