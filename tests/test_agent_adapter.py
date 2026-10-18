"""Tests for coding agent adapters, zero-spend budget enforcement, and evidence store."""
import tempfile
import unittest
from pathlib import Path

from software_factory.agent_adapter import (
    AgentBudget,
    AutoSelectAgentAdapter,
    DeterministicAgentAdapter,
    FreeQuotaAgentAdapter,
    GeminiFreeAgentAdapter,
    GroqFreeAgentAdapter,
    HeuristicSynthesisAdapter,
    OllamaAgentAdapter,
    OpenHandsAgentAdapter,
    QuotaExhaustedError,
)
from software_factory.evidence_store import EvidenceStore


class AgentAdapterAndEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.tmp.name)
        self.db_path = self.base_dir / "evidence.sqlite3"
        self.store = EvidenceStore(self.db_path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_agent_budget_enforces_strict_zero_spend(self):
        budget = AgentBudget(max_agent_calls=2, max_tokens=1000)
        budget.check_call_allowed()

        # Non-zero cost must immediately raise QuotaExhaustedError
        with self.assertRaises(QuotaExhaustedError):
            budget.record_usage(tokens=100, cost_usd=0.01)

        # Valid zero-cost call succeeds
        budget.record_usage(tokens=400, cost_usd=0.0)
        self.assertEqual(budget.calls_made, 1)
        self.assertEqual(budget.tokens_used, 400)
        self.assertEqual(budget.cost_usd, 0.0)

        # Second call succeeds
        budget.check_call_allowed()
        budget.record_usage(tokens=500, cost_usd=0.0)
        self.assertEqual(budget.calls_made, 2)

        # Exceeding calls raises QuotaExhaustedError
        with self.assertRaises(QuotaExhaustedError):
            budget.check_call_allowed()

    def test_deterministic_agent_adapter_generates_valid_artifacts(self):
        adapter = DeterministicAgentAdapter()
        budget = AgentBudget()

        resp = adapter.generate(
            prompt="Generate order dispatch schema",
            context={"task_id": "dispatch-schema", "squad": "rider_dispatch", "input": {"path": "rider/dispatch.ts"}},
            budget=budget,
        )
        self.assertEqual(resp.status, "COMPLETED")
        self.assertEqual(resp.cost_usd, 0.0)
        self.assertIn("rider/dispatch.ts", resp.files_modified)
        self.assertIn("export interface", resp.code)
        self.assertGreater(budget.tokens_used, 0)

    def test_free_quota_agent_adapter_and_openhands_adapter(self):
        free_adapter = FreeQuotaAgentAdapter()
        budget = AgentBudget()
        resp = free_adapter.generate("Build customer screen", {"task_id": "cust-1"}, budget)
        self.assertEqual(resp.status, "COMPLETED")
        self.assertEqual(resp.cost_usd, 0.0)

        oh_adapter = OpenHandsAgentAdapter()
        resp_oh = oh_adapter.generate("Build login component", {"task_id": "login-comp"}, budget)
        self.assertEqual(resp_oh.status, "COMPLETED")
        self.assertIn("React", resp_oh.code)

    def test_evidence_store_records_diffs_and_test_logs(self):
        diff_record = self.store.record_diff(
            job_id="job-100",
            task_id="task-1",
            attempt_id="att-1",
            file_path="src/index.ts",
            before_content="const a = 1;\n",
            after_content="const a = 1;\nconst b = 2;\n",
        )
        self.assertEqual(diff_record["payload"]["additions"], 1)
        self.assertEqual(diff_record["payload"]["deletions"], 0)
        self.assertIn("+const b = 2;", diff_record["payload"]["diff_text"])

        test_log = self.store.record_test_log(
            job_id="job-100",
            task_id="task-1",
            attempt_id="att-1",
            command="pytest tests",
            exit_code=0,
            stdout="10 passed",
            stderr="",
            duration_ms=45,
        )
        self.assertTrue(test_log["payload"]["passed"])

        self.store.record_budget_event(
            job_id="job-100",
            task_id="task-1",
            attempt_id="att-1",
            tokens_used=250,
            cost_usd=0.0,
        )

        summary = self.store.get_summary("job-100")
        self.assertEqual(summary["diffs_count"], 1)
        self.assertEqual(summary["total_lines_added"], 1)
        self.assertEqual(summary["tests_run"], 1)
        self.assertEqual(summary["tests_passed"], 1)
        self.assertEqual(summary["tokens_consumed"], 250)
        self.assertEqual(summary["total_spend_usd"], 0.0)
        self.assertTrue(summary["zero_spend_compliant"])

    def test_heuristic_synthesis_adapter_generates_domain_logic(self):
        adapter = HeuristicSynthesisAdapter()
        budget = AgentBudget()

        # Parent tracking screen
        resp_parent = adapter.generate(
            "Build parent tracking screen for school bus route 4",
            {"task_id": "parent-track"},
            budget,
        )
        self.assertEqual(resp_parent.status, "COMPLETED")
        self.assertIn("ParentLiveTrackingScreen", resp_parent.code)
        self.assertIn("BusLocation", resp_parent.code)

        # Driver attendance screen
        resp_driver = adapter.generate(
            "Build driver QR attendance scanner screen",
            {"task_id": "driver-att"},
            budget,
        )
        self.assertIn("DriverAttendanceScreen", resp_driver.code)
        self.assertIn("StudentAttendee", resp_driver.code)

    def test_gemini_and_groq_fallback_when_no_api_key(self):
        budget = AgentBudget()
        gemini = GeminiFreeAgentAdapter(api_key="")
        resp_g = gemini.generate("Create school bus admin dashboard", {"task_id": "admin-fleet"}, budget)
        self.assertEqual(resp_g.status, "COMPLETED")
        self.assertIn("SchoolFleetAdminConsole", resp_g.code)

        groq = GroqFreeAgentAdapter(api_key="")
        resp_gr = groq.generate("Create parent screen", {"task_id": "parent"}, budget)
        self.assertEqual(resp_gr.status, "COMPLETED")

    def test_autoselect_adapter_falls_back_cleanly(self):
        budget = AgentBudget()
        auto = AutoSelectAgentAdapter(preferred_provider="auto")
        resp = auto.generate("Build emergency SOS alert", {"task_id": "sos"}, budget)
        self.assertEqual(resp.status, "COMPLETED")
        self.assertEqual(resp.cost_usd, 0.0)


if __name__ == "__main__":
    unittest.main()


