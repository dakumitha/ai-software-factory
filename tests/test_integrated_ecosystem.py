"""Comprehensive test suite for the 6 integrated agentic repositories:
1. FreeLLMAPI (Multi-Provider Smart Routing & Zero-Spend Failover)
2. Claude-Mem (Persistent Memory & Progressive Disclosure)
3. Strix (Autonomous Security Auditor & Penetration Testing Gate)
4. Agent-Reach (Zero-Cost External Documentation & Schema Reach)
5. Awesome-Claws (Multi-Channel Webhook & Chat Claw Bridge)
6. Claude-Code-Setup / ASE (Standardized Agent Environment & CLAUDE.md)
"""
import json
import tempfile
import unittest
from pathlib import Path

from software_factory.agent_adapter import AgentBudget, AgentResponse, CodingAgentAdapter, QuotaExhaustedError
from software_factory.agent_standards import AgentEnvironmentBootstrapper
from software_factory.claws import ClawBridge, ClawCommand
from software_factory.core import Store
from software_factory.free_router import FreeLlmRouter
from software_factory.memory import AgentMemoryStore
from software_factory.reach import AgentReachEngine
from software_factory.security import SecurityAuditEngine


class FailingProvider(CodingAgentAdapter):
    def __init__(self, name: str = "failing-provider", is_rate_limit: bool = True):
        self._name = name
        self._is_rate_limit = is_rate_limit

    @property
    def adapter_name(self) -> str:
        return self._name

    def generate(self, prompt: str, context: dict, budget: AgentBudget) -> AgentResponse:
        budget.check_call_allowed()
        if self._is_rate_limit:
            raise QuotaExhaustedError("Rate limit 429 hit")
        raise RuntimeError("Network failure")


class MockSuccessProvider(CodingAgentAdapter):
    def __init__(self, name: str = "success-provider"):
        self._name = name

    @property
    def adapter_name(self) -> str:
        return self._name

    def generate(self, prompt: str, context: dict, budget: AgentBudget) -> AgentResponse:
        budget.check_call_allowed()
        budget.record_usage(tokens=50, cost_usd=0.0)
        return AgentResponse(
            code="export const live = true;",
            files_modified={"src/index.ts": "export const live = true;"},
            tokens_used=50,
            cost_usd=0.0,
            explanation=f"Generated via {self._name}",
            status="COMPLETED",
        )


class IntegratedEcosystemTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.tmp.name)
        self.db_path = self.base_dir / "factory.sqlite3"
        self.store = Store(self.db_path)

    def tearDown(self):
        import gc
        gc.collect()
        try:
            self.tmp.cleanup()
        except Exception:
            pass

    # 1. FreeLLMAPI Test
    def test_free_llm_router_fails_over_cleanly(self):
        failing = FailingProvider(name="mock-gemini-rate-limited", is_rate_limit=True)
        backup = MockSuccessProvider(name="mock-groq-backup")
        router = FreeLlmRouter(providers=[failing, backup], name="test-router")

        budget = AgentBudget()
        resp = router.generate("Build route tracker", {}, budget)

        self.assertEqual(resp.status, "COMPLETED")
        self.assertIn("mock-groq-backup", resp.explanation)
        self.assertEqual(budget.cost_usd, 0.0)

        health = router.get_health_status()
        self.assertFalse(health["mock-gemini-rate-limited"]["healthy"])
        self.assertTrue(health["mock-groq-backup"]["healthy"])

    # 2. Claude-Mem Test
    def test_agent_memory_store_persists_and_queries(self):
        mem_store = AgentMemoryStore(self.db_path)
        mem_id = mem_store.record_memory(
            job_id="job-42",
            task_id="task-arch",
            category="architecture",
            summary="Decided on Firestore collection naming for students and routes",
            details="Collections: 'students', 'routes', 'attendance_logs'",
            tags=["firestore", "database", "school_transport"],
        )
        self.assertGreater(mem_id, 0)

        results = mem_store.query_memories(job_id="job-42", query="firestore")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["category"], "architecture")

        # Test Progressive Context Generation
        context_header = mem_store.get_progressive_context("job-42", "How do I query student routes in firestore?")
        self.assertIn("PROGRESSIVE CONTEXT", context_header)
        self.assertIn("Decided on Firestore collection naming", context_header)

    # 3. Strix Security Audit Test
    def test_strix_security_auditor_detects_flaws(self):
        auditor = SecurityAuditEngine()
        ws_dir = self.base_dir / "workspace-audit"
        ws_dir.mkdir(parents=True)

        # Write clean file
        (ws_dir / "clean.ts").write_text("export const pi = 3.14159;\n", encoding="utf-8")
        clean_rep = auditor.audit_workspace(ws_dir, job_id="clean-job")
        self.assertEqual(clean_rep.status, "PASSED")
        self.assertEqual(clean_rep.risk_level, "CLEAN")

        # Inject dangerous patterns
        (ws_dir / "insecure.rules").write_text(
            "service cloud.firestore { match /{document=**} { allow read, write: if true; } }",
            encoding="utf-8",
        )
        (ws_dir / "bad_component.tsx").write_text(
            "export function Comp() { return <div dangerouslySetInnerHTML={{ __html: 'test' }} />; }",
            encoding="utf-8",
        )

        vuln_rep = auditor.audit_workspace(ws_dir, job_id="vuln-job")
        self.assertEqual(vuln_rep.status, "FAILED_SECURITY_GATE")
        self.assertIn(vuln_rep.risk_level, ("CRITICAL", "HIGH"))
        self.assertGreaterEqual(vuln_rep.total_findings, 2)

    # 4. Agent-Reach Test
    def test_agent_reach_offline_contracts(self):
        reach = AgentReachEngine()
        contract = reach.get_contract("firebase-firestore")
        self.assertIsNotNone(contract)
        self.assertEqual(contract.title, "Firebase Firestore Web SDK v9 Modular API Contract")
        self.assertIn("getFirestore", contract.schema_definitions["methods"])

        rzp = reach.get_contract("razorpay_checkout")
        self.assertIsNotNone(rzp)
        self.assertIn("HMAC-SHA256", rzp.schema_definitions["verification_algorithm"])

    # 5. Awesome-Claws Webhook Test
    def test_claws_bridge_processes_chat_commands(self):
        bridge = ClawBridge(self.store, webhook_secret="")

        # Test /status command
        cmd_status = ClawCommand(
            action="status",
            args=[],
            sender_id="@superadmin",
            channel="telegram",
            raw_text="/status",
        )
        resp_status = bridge.execute_command(cmd_status)
        self.assertTrue(resp_status.success)
        self.assertIn("AI Software Factory Status", resp_status.markdown_text)

        # Test /build command
        cmd_build = ClawCommand(
            action="build",
            args=["school_transport"],
            sender_id="@operator",
            channel="discord",
            raw_text="/build school_transport",
        )
        resp_build = bridge.execute_command(cmd_build)
        self.assertTrue(resp_build.success)
        self.assertIn("New Job Initialized", resp_build.markdown_text)
        self.assertIn("job_id", resp_build.data)

    # 6. Claude-Code-Setup / ASE Standards Test
    def test_agent_environment_bootstrapper_writes_standards(self):
        bootstrapper = AgentEnvironmentBootstrapper()
        target_ws = self.base_dir / "target-workspace"
        written = bootstrapper.bootstrap_workspace(target_ws, project_title="VidyaVahan School Transport")

        self.assertEqual(len(written), 3)
        self.assertTrue((target_ws / "CLAUDE.md").exists())
        self.assertTrue((target_ws / "AGENT.md").exists())
        self.assertTrue((target_ws / ".agent" / "config.json").exists())

        claude_content = (target_ws / "CLAUDE.md").read_text(encoding="utf-8")
        self.assertIn("VidyaVahan School Transport", claude_content)
        self.assertIn("Zero-Spend Constraint", claude_content)


if __name__ == "__main__":
    unittest.main()

