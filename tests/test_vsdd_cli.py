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
            base = Path(tmp)
            state = json.loads((base / ".vsdd/changes/add-demo/state.json").read_text())
            self.assertEqual(state["stage"], "intake")
            self.assertTrue((base / ".vsdd/changes/add-demo/feature-spec.md").exists())
            self.assertTrue((base / ".vsdd/changes/add-demo/source-register.md").exists())
            graph = json.loads((base / ".vsdd/changes/add-demo/traceability.json").read_text())
            self.assertEqual(graph["changeId"], "add-demo")
            self.assertEqual(graph["nodes"], [])
            self.assertTrue((base / ".vsdd/schemas/traceability.schema.json").exists())
            self.assertTrue((base / ".agents/skills/vsdd-orchestrate/SKILL.md").exists())
            self.assertTrue((base / ".agents/skills/vsdd-capabilities/SKILL.md").exists())

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
            "- Feature ID: FB-001\n- Source: product request\n- Status: proposed\n", encoding="utf-8")
        (folder / "source-register.md").write_text(
            "- Coverage review: confirmed\n- Reviewed by: Product Owner\n- Review record: REVIEW-100\n\n"
            "| Source ID | Source type | Location / revision | Requirement or intent | Disposition | Rationale / owner |\n"
            "|---|---|---|---|---|---|\n"
            "| SRC-001 | PRD | prd.md v1 | User can request a status display | in-scope | Product Owner |\n",
            encoding="utf-8")
        (folder / "feature-spec.md").write_text(
            "### FR-001: Display status\nGiven a valid state, when requested, then display it.\n\n"
            "- AC-001: Status is visible.\n\n"
            "| dimension | applicability | FR / AC IDs | rationale / evidence | review record |\n"
            "|---|---|---|---|---|\n"
            + "| normal | applicable | FR-001 / AC-001 | Reviewed for this test fixture | REVIEW-100 |\n| boundary | applicable | FR-001 / AC-001 | Reviewed for this test fixture | REVIEW-100 |\n| invalid-input | applicable | FR-001 / AC-001 | Reviewed for this test fixture | REVIEW-100 |\n| state-transition | applicable | FR-001 / AC-001 | Reviewed for this test fixture | REVIEW-100 |\n| failure | applicable | FR-001 / AC-001 | Reviewed for this test fixture | REVIEW-100 |\n| recovery | applicable | FR-001 / AC-001 | Reviewed for this test fixture | REVIEW-100 |\n| timing-performance | applicable | FR-001 / AC-001 | Reviewed for this test fixture | REVIEW-100 |\n| interface-semantics | applicable | FR-001 / AC-001 | Reviewed for this test fixture | REVIEW-100 |\n| safety-security-diagnostics | applicable | FR-001 / AC-001 | Reviewed for this test fixture | REVIEW-100 |" + "\n", encoding="utf-8")
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
        (folder / "tasks.md").write_text(
            "| Task ID | Requirement | Action | Path | Test | Status |\n|---|---|---|---|---|---|\n"
            "| T-001 | SWE-001 | Implement display | src/display.c | TC-001 | proposed |\n", encoding="utf-8")
        (folder / "verification.md").write_text(
            "| Test ID | Requirement | Level | Environment | Command/procedure | Expected criteria | Actual result | Status | Evidence |\n"
            "|---|---|---|---|---|---|---|---|---|\n"
            "| TC-001 | SWE-001 | unit | Host | pytest tests/test_display.py | status visible | Not run | planned | TBD |\n",
            encoding="utf-8")

        def node(id, type, title, artifact, **kwargs):
            return {"id": id, "type": type, "title": title, "artifact": artifact, "anchor": id, **kwargs}
        base = ""
        nodes = [
            node("FB-001", "feature", "Display status", base+"feature-brief.md"),
            node("SRC-001", "source", "User requests a status display", base+"source-register.md", scope="in-scope"),
            node("FR-001", "feature-requirement", "Display status", base+"feature-spec.md"),
            node("AC-001", "acceptance-criterion", "Status is visible", base+"feature-spec.md"),
            node("SYS-001", "system-requirement", "Display status", base+"system-requirements.md"),
            node("ARCH-001", "architecture-element", "Display boundary", base+"architecture.md"),
            node("SWE-001", "software-requirement", "Render status", base+"software-requirements.md"),
            node("T-001", "task", "Implement display", base+"tasks.md"),
            node("TC-001", "test-case", "Display status test", base+"verification.md"),
        ]
        def edge(id, source, target, type):
            return {"id": id, "source": source, "target": target, "type": type, "status": "proposed",
                    "evidence": [{"artifact": base+"traceability.json", "note": "Trace mapping reviewed in test fixture"}]}
        edges = [
            edge("TR-001","SRC-001","FR-001","derives"),
            edge("TR-002","FB-001","FR-001","decomposes-into"),
            edge("TR-003","FR-001","AC-001","has-acceptance-criteria"),
            edge("TR-004","AC-001","SYS-001","derives"),
            edge("TR-005","SYS-001","ARCH-001","allocated-to"),
            edge("TR-006","SYS-001","SWE-001","allocated-to"),
            edge("TR-007","SWE-001","T-001","implemented-by"),
            edge("TR-008","SWE-001","TC-001","verified-by"),
        ]
        graph = {"schemaVersion":"1.0","changeId":"trace-demo","nodes":nodes,"edges":edges}
        (folder / "traceability.json").write_text(json.dumps(graph, indent=2), encoding="utf-8")
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
            path = folder / "traceability.json"
            graph = json.loads(path.read_text())
            graph["edges"] = [e for e in graph["edges"] if not (e["source"] == "SYS-001" and e["target"] == "SWE-001")]
            path.write_text(json.dumps(graph, indent=2), encoding="utf-8")
            result = self.run_cli("trace-check", "trace-demo", "--root", tmp)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("incomplete trace coverage", result.stdout)

    def test_trace_check_detects_dangling_edge(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = self.prepare_planned_feature(Path(tmp))
            path = folder / "traceability.json"
            graph = json.loads(path.read_text())
            graph["edges"].append({
                "id":"TR-999","source":"FR-001","target":"AC-999","type":"has-acceptance-criteria",
                "status":"proposed","evidence":[{"artifact":"traceability.json","note":"deliberately dangling edge"}]
            })
            path.write_text(json.dumps(graph, indent=2), encoding="utf-8")
            result = self.run_cli("trace-check", "trace-demo", "--root", tmp)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("dangling edge", result.stdout)

    def test_trace_traverses_bidirectionally(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = self.prepare_planned_feature(Path(tmp))
            result = self.run_cli("trace", "trace-demo", "--id", "FB-001", "--root", tmp)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("FB-001 --decomposes-into", result.stdout)
            self.assertIn("SWE-001 --verified-by", result.stdout)
            self.assertIn("direction=both", result.stdout)

if __name__ == "__main__":
    unittest.main()
