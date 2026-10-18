"""Tests for dynamic multi-agent swarm decomposition and concurrent execution pool."""
import json
import tempfile
import time
import unittest
from pathlib import Path

from software_factory.artifact_task import handle_artifact_integrity_task
from software_factory.core import Store
from software_factory.swarm import (
    SQUAD_BACKEND,
    SQUAD_CUSTOMER_MOBILE,
    SQUAD_CUSTOMER_WEB,
    SQUAD_QA_VERIFICATION,
    SwarmExecutionPool,
    decompose_to_swarm_tasks,
)


class SwarmTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.tmp.name)
        self.db_path = self.base_dir / "swarm.sqlite3"
        self.workspace = self.base_dir / "workspace"
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.store = Store(self.db_path)
        self.project = self.store.create_project("Swarm Marketplace", "Multi-squad platform test")

    def tearDown(self):
        self.tmp.cleanup()

    def test_decompose_to_swarm_tasks_creates_multi_squad_dag(self):
        spec = {"title": "Amazon-Flipkart Hybrid Marketplace"}
        tasks = decompose_to_swarm_tasks(
            spec,
            squads=[SQUAD_BACKEND, SQUAD_CUSTOMER_WEB, SQUAD_CUSTOMER_MOBILE],
            tasks_per_squad=2,
        )

        # 1 foundation + (3 squads * 2 tasks) + 1 QA = 8 tasks
        self.assertEqual(len(tasks), 8)

        # Foundation has no dependencies
        foundation = next(t for t in tasks if t["id"] == "foundation-schema")
        self.assertEqual(foundation["depends_on"], [])

        # All squad tasks depend on foundation
        squad_tasks = [t for t in tasks if t["id"] not in {"foundation-schema", "qa-integration-verification"}]
        self.assertEqual(len(squad_tasks), 6)
        for t in squad_tasks:
            self.assertEqual(t["depends_on"], ["foundation-schema"])

        # QA task depends on all squad tasks
        qa_task = next(t for t in tasks if t["id"] == "qa-integration-verification")
        self.assertEqual(set(qa_task["depends_on"]), {t["id"] for t in squad_tasks})

    def test_swarm_pool_executes_parallel_tasks_concurrently(self):
        spec = {"title": "Multi-Stakeholder Marketplace"}
        squads = [SQUAD_BACKEND, SQUAD_CUSTOMER_WEB, SQUAD_CUSTOMER_MOBILE]
        tasks = decompose_to_swarm_tasks(spec, squads=squads, tasks_per_squad=2)

        job = self.store.create_job(
            self.project["id"],
            tasks=tasks,
            budget={"max_agent_calls": 50, "max_runtime_seconds": 60},
        )
        for s in ("NEEDS_CLARIFICATION", "SPEC_READY", "PLAN_READY", "AWAITING_APPROVAL", "QUEUED", "RUNNING"):
            self.store.transition(job["id"], s)

        pool = SwarmExecutionPool(
            self.store,
            job["id"],
            self.workspace,
            max_workers=4,
            heartbeat_interval=0.03,
        )

        def handler(payload):
            time.sleep(0.01)  # tiny sleep to simulate parallel micro-agent work
            return handle_artifact_integrity_task(self.workspace, payload["input"])

        telemetry = pool.run_swarm_until_complete(handler)

        self.assertEqual(telemetry["total_tasks_count"], 8)
        self.assertEqual(telemetry["completed_tasks_count"], 8)
        self.assertEqual(telemetry["failed_tasks_count"], 0)
        self.assertEqual(telemetry["active_subagents_count"], 0)
        self.assertEqual(telemetry["circuit_breaker_state"], "CLOSED")

        # Verify on-disk files were generated across squads
        for t in tasks:
            art_file = self.workspace / t["input"]["path"]
            self.assertTrue(art_file.exists(), f"Artifact file missing: {art_file}")
            content = json.loads(art_file.read_text(encoding="utf-8"))
            self.assertTrue(content.get("verified") or content.get("all_tests_passed") or "models" in content)

    def test_swarm_pool_handles_subagent_failure_gracefully(self):
        tasks = [
            {
                "id": "task-good-1",
                "title": "Good Task 1",
                "squad": "test",
                "type": "custom",
                "depends_on": [],
                "input": {"ok": True},
            },
            {
                "id": "task-bad-1",
                "title": "Failing Task",
                "squad": "test",
                "type": "custom",
                "depends_on": [],
                "input": {"fail": True},
            },
        ]
        job = self.store.create_job(self.project["id"], tasks=tasks)
        for s in ("NEEDS_CLARIFICATION", "SPEC_READY", "PLAN_READY", "AWAITING_APPROVAL", "QUEUED", "RUNNING"):
            self.store.transition(job["id"], s)

        pool = SwarmExecutionPool(self.store, job["id"], self.workspace, max_workers=2)

        def handler(payload):
            if payload["input"].get("fail"):
                raise RuntimeError("Micro-agent simulation error")
            return {"result": "success"}

        telemetry = pool.run_swarm_until_complete(handler, max_total_steps=10)
        self.assertEqual(telemetry["completed_tasks_count"], 1)
        self.assertEqual(telemetry["failed_tasks_count"], 1)
        self.assertIn("task-bad-1", pool._failed_tasks)


if __name__ == "__main__":
    unittest.main()

