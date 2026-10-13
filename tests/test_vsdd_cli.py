import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "vsdd.py"

DIMENSIONS = [
    "normal", "boundary", "invalid-input", "state-transition", "failure",
    "recovery", "timing-performance", "interface-semantics", "safety-security-diagnostics",
]

class VSDDCLITests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), *args], text=True, capture_output=True)

    def test_init_and_new_scaffold(self):
        with tempfile.TemporaryDirectory() as tmp:
            init = self.run_cli("init", "--root", tmp)
            self.assertEqual(init.returncode, 0, init.stderr)
            created = self.run_cli("new", "add-demo", "--root", tmp)
            self.assertEqual(created.returncode, 0, created.stderr)
            base = Path(tmp)
            state = json.loads((base / ".vsdd/changes/add-demo/state.json").read_text())
            self.assertEqual(state["stage"], "intake")
            self.assertTrue((base / ".vsdd/changes/add-demo/feature-spec.md").exists())
            self.assertTrue((base / ".vsdd/changes/add-demo/source-register.md").exists())
            self.assertTrue((base / ".agents/skills/vsdd-orchestrate/SKILL.md").exists())
            self.assertTrue((base / ".agents/skills/vsdd-capabilities/SKILL.md").exists())
            self.assertTrue((base / ".vsdd/templates/feature-spec.md").exists())

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

    def prepare_planned_feature(self, root):
        result = self.run_cli("init", "--root", str(root))
        self.assertEqual(result.returncode, 0, result.stderr)
        result = self.run_cli("new", "trace-demo", "--root", str(root))
        self.assertEqual(result.returncode, 0, result.stderr)
        folder = root / ".vsdd/changes/trace-demo"
        (folder / "feature-brief.md").write_text(
            "- Feature ID: FB-001\n- Source: product request\n- Status: proposed\n",
            encoding="utf-8")
        (folder / "source-register.md").write_text(
            "- Coverage review: confirmed\n- Reviewed by: Product Owner\n- Review record: REVIEW-100\n\n"
            "| Source ID | Source type | Location / revision | Requirement or intent | Disposition | Rationale / owner |\n"
            "|---|---|---|---|---|---|\n"
            "| SRC-001 | PRD | prd.md v1 | User can request a status display | in-scope | Product Owner |\n",
            encoding="utf-8")
        completeness = "\n".join(
            f"| {dim} | applicable | FR-001 / AC-001 | Reviewed for this fixture | REVIEW-100 |"
            for dim in DIMENSIONS)
        (folder / "feature-spec.md").write_text(
            "### FR-001: Display status\nGiven a valid state, when requested, then display it.\n\n"
            "- AC-001: Status is visible.\n\n"
            "| dimension | applicability | FR / AC IDs | rationale / evidence | review record |\n"
            "|---|---|---|---|---|\n" + completeness + "\n",
            encoding="utf-8")
        (folder / "capability-map.md").write_text("# Capability map\nExisting capability checked.\n", encoding="utf-8")
        (folder / "system-requirements.md").write_text(
            "| ID | Requirement | Source | Verification | Status |\n|---|---|---|---|---|\n"
            "| SYS-001 | Display status | AC-001 | Test | proposed |\n", encoding="utf-8")
        (folder / "architecture.md").write_text(
            "| ARCH ID | Element | Responsibility | SYS ID | Status |\n|---|---|---|---|---|\n"
            "| ARCH-001 | Display boundary | Render status | SYS-001 | proposed |\n", encoding="utf-8")
        (folder / "software-requirements.md").write_text(
            "| ID | Requirement | SYS | Component | Verification | Status |\n|---|---|---|---|---|---|\n"
            "| SWE-001 | Render status | SYS-001 | Display | TC-001 | proposed |\n", encoding="utf-8")
        (folder / "tasks.md").write_text("- [ ] T-001 Implement display status; SWE-001; TC-001.\n", encoding="utf-8")
        (folder / "verification.md").write_text(
            "| Test/evidence ID | Requirement/AC | Environment | Command/procedure | Actual result | Status | Evidence |\n"
            "|---|---|---|---|---|---|---|\n"
            "| TC-001 | SWE-001 | Host | pytest tests/test_display.py | Not run | planned | TBD |\n",
            encoding="utf-8")
        (folder / "traceability.csv").write_text(
            "source_id,target_id,relationship,status,evidence\n"
            "FB-001,FR-001,decomposes-into,proposed,brief\n"
            "SRC-001,FR-001,derives,proposed,prd\n"
            "FR-001,AC-001,constrains,proposed,acceptance\n"
            "AC-001,SYS-001,derives,proposed,system\n"
            "SYS-001,ARCH-001,allocated-to,proposed,architecture\n"
            "SYS-001,SWE-001,allocated-to,proposed,software\n"
            "SWE-001,T-001,implemented-by,proposed,task\n"
            "SWE-001,TC-001,verified-by,proposed,test\n", encoding="utf-8")
        state_file = folder / "state.json"
        state = json.loads(state_file.read_text(encoding="utf-8"))
        state["stage"] = "planned"
        state_file.write_text(json.dumps(state), encoding="utf-8")
        return folder

    def test_trace_check_accepts_complete_planned_trace(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.prepare_planned_feature(Path(tmp))
            result = self.run_cli("trace-check", "trace-demo", "--root", tmp)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("traceability at planned: PASS", result.stdout)

    def test_trace_check_detects_missing_software_allocation(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = self.prepare_planned_feature(Path(tmp))
            trace = folder / "traceability.csv"
            trace.write_text(trace.read_text().replace(
                "SYS-001,SWE-001,allocated-to,proposed,software\n", ""), encoding="utf-8")
            result = self.run_cli("trace-check", "trace-demo", "--root", tmp)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("missing outgoing trace to SWE-*", result.stdout)

if __name__ == "__main__":
    unittest.main()
