import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "vsdd.py"

class VSDDCLITests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), *args], text=True, capture_output=True)

    def test_init_and_new_scaffold(self):
        with tempfile.TemporaryDirectory() as tmp:
            init = self.run_cli("init", "--root", tmp)
            self.assertEqual(init.returncode, 0, init.stderr)
            created = self.run_cli("new", "add-demo", "--root", tmp)
            self.assertEqual(created.returncode, 0, created.stderr)
            state = json.loads((Path(tmp) / ".vsdd/changes/add-demo/state.json").read_text())
            self.assertEqual(state["stage"], "intake")
            self.assertTrue((Path(tmp) / ".vsdd/changes/add-demo/feature-spec.md").exists())

    def test_invalid_slug_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.run_cli("init", "--root", tmp)
            result = self.run_cli("new", "Bad Name", "--root", tmp)
            self.assertNotEqual(result.returncode, 0)

    def test_stage_cannot_be_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.run_cli("init", "--root", tmp)
            self.run_cli("new", "add-demo", "--root", tmp)
            result = self.run_cli("advance", "add-demo", "--to", "planned", "--root", tmp)
            self.assertNotEqual(result.returncode, 0)

if __name__ == "__main__":
    unittest.main()
