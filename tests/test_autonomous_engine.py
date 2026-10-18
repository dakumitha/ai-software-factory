"""Tests for AutonomousCodingEngine, syntax verification, and self-healing reflection."""
import tempfile
import unittest
from pathlib import Path

from software_factory.agent_adapter import AgentBudget, AgentResponse, CodingAgentAdapter
from software_factory.autonomous_engine import (
    AutonomousCodingEngine,
    verify_code_syntax,
)
from software_factory.evidence_store import EvidenceStore
from software_factory.sandbox import IsolatedWorkspace


class MockSelfHealingAdapter(CodingAgentAdapter):
    """Mock adapter that produces broken code on iteration 1, then fixes it on iteration 2."""

    def __init__(self):
        self.call_count = 0

    @property
    def adapter_name(self) -> str:
        return "mock-self-healing"

    def generate(self, prompt: str, context: dict, budget: AgentBudget) -> AgentResponse:
        self.call_count += 1
        budget.record_usage(tokens=100, cost_usd=0.0)

        # Iteration 1 returns broken unclosed bracket code
        if self.call_count == 1:
            code = "export function broken() { return (<div>"
        else:
            code = "export function fixed() { return <div>Fixed</div>; }"

        return AgentResponse(
            code=code,
            files_modified={context.get("input", {}).get("path", "src/app.tsx"): code},
            tokens_used=100,
            cost_usd=0.0,
            status="COMPLETED",
        )


class AutonomousEngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.tmp.name)
        self.ws_dir = self.base_dir / "workspace"
        self.ws_dir.mkdir(parents=True)
        self.workspace = IsolatedWorkspace(self.ws_dir)
        self.evidence_store = EvidenceStore(self.base_dir / "evidence.sqlite3")

    def tearDown(self):
        self.tmp.cleanup()

    def test_verify_code_syntax_python_and_ts(self):
        # Python syntax
        passed, _ = verify_code_syntax("test.py", "def add(a, b):\n    return a + b\n")
        self.assertTrue(passed)

        failed, err = verify_code_syntax("test.py", "def add(a, b\n    return a + b\n")
        self.assertFalse(failed)
        self.assertIn("SyntaxError", err)

        # TypeScript syntax
        ts_valid = "export interface Student { id: string; name: string; }\n"
        passed_ts, _ = verify_code_syntax("student.ts", ts_valid)
        self.assertTrue(passed_ts)

        ts_broken = "export interface Student { id: string; name: string;\n"
        failed_ts, err_ts = verify_code_syntax("student.ts", ts_broken)
        self.assertFalse(failed_ts)
        self.assertIn("Unclosed", err_ts)

    def test_autonomous_coding_loop_recovers_via_reflection(self):
        adapter = MockSelfHealingAdapter()
        engine = AutonomousCodingEngine(
            adapter=adapter,
            evidence_store=self.evidence_store,
            max_repair_iterations=3,
        )

        receipt = engine.execute_autonomous_task(
            workspace=self.workspace,
            job_id="job-autofix",
            task_id="task-1",
            prompt="Build student badge widget",
            target_file="src/badge.tsx",
        )

        # Verified that it detected the error in iteration 1 and repaired in iteration 2
        self.assertEqual(receipt["status"], "VERIFIED")
        self.assertEqual(receipt["iterations_used"], 2)
        self.assertFalse(receipt["attempts"][0]["verified"])
        self.assertTrue(receipt["attempts"][1]["verified"])
        self.assertTrue(self.workspace.file_exists("src/badge.tsx"))
        self.assertIn("Fixed", self.workspace.read_file("src/badge.tsx"))

        # Verify evidence store recorded diffs
        evidence = self.evidence_store.get_summary("job-autofix")
        self.assertGreaterEqual(evidence["diffs_count"], 2)
        self.assertTrue(evidence["zero_spend_compliant"])

    def test_preview_bundle_renders_valid_html(self):
        from software_factory.preview import render_preview_bundle
        html_doc = render_preview_bundle(project_title="VidyaVahan Test")
        self.assertIn("<!DOCTYPE html>", html_doc)
        self.assertIn("Parent Portal", html_doc)
        self.assertIn("Driver Console", html_doc)
        self.assertIn("School Transport Operations Dashboard", html_doc)
        self.assertIn("Aarav Sharma", html_doc)


if __name__ == "__main__":
    unittest.main()

