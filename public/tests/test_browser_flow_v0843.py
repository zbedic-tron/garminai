"""Simulated browser login callback regression checks (requires node locally)."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import pytest
from garminai_public.auth_staging_poc import _JS


def test_browser_flow():
    if shutil.which('node') is None:
        pytest.skip('Node.js is not installed in this test environment')
    script = Path(__file__).resolve().parent / 'js' / 'test_login_flow.cjs'
    with tempfile.TemporaryDirectory() as directory:
        jsfile = Path(directory) / 'staging.js'
        jsfile.write_text(_JS, encoding='utf8')
        result = subprocess.run(['node', str(script), str(jsfile)], capture_output=True, text=True, timeout=12)
    assert result.returncode == 0, result.stdout + '\n' + result.stderr
