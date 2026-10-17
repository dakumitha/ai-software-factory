"""Tests for background heartbeat renewal and structured task outcomes."""
import tempfile
import time
import unittest
from pathlib import Path

from software_factory.core import Store
from software_factory.execution import ExecutionController
from software_factory.heartbeat import (
    OUTCOME_HANDLER_ERROR,
    OUTCOME_OUTPUT_LIMIT_EXCEEDED,
    OUTCOME_SUCCESS,
    OUTCOME_TIMEOUT,
    HeartbeatKeeper,
    build_task_outcome,
    sanitize_error,
)


class HeartbeatAndOutcomeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "heartbeat_test.sqlite3"
        self.store = Store(self.db_path)
        self.project = self.store.create_project("Heartbeat Project", "Test heartbeat keeper")
        self.job = self.store.create_job(
            self.project["id"],
            tasks=[
                {"id": "task-1-slow", "title": "Slow Task", "type": "slow_task", "input": {"wait": 0.05}},
                {"id": "task-2-fail", "title": "Failing Task", "type": "failing_task", "input": {}},
            ],
        )
        for s in ["NEEDS_CLARIFICATION", "SPEC_READY", "PLAN_READY", "AWAITING_APPROVAL", "QUEUED", "RUNNING"]:
            self.store.transition(self.job["id"], s)

    def tearDown(self):
        self.tmp.cleanup()

    def test_sanitize_error_redacts_credentials(self):
        raw_error = "Failed to connect with Bearer abcdef1234567890. Secret api_key=supersecret123 and token='my_secret_token'"
        sanitized = sanitize_error(raw_error)

        self.assertNotIn("abcdef1234567890", sanitized)
        self.assertNotIn("supersecret123", sanitized)
        self.assertNotIn("my_secret_token", sanitized)
        self.assertIn("Bearer [REDACTED]", sanitized)
        self.assertIn("api_key=[REDACTED]", sanitized)

    def test_build_task_outcome_retry_eligibility(self):
        success = build_task_outcome(OUTCOME_SUCCESS, 150, "task-1", "attempt-1")
        self.assertFalse(success["retry_eligible"])
        self.assertEqual(success["category"], OUTCOME_SUCCESS)
        self.assertEqual(success["duration_ms"], 150)

        handler_err = build_task_outcome(
            OUTCOME_HANDLER_ERROR, 200, "task-1", "attempt-2", error="DNS timeout Bearer 123456789012"
        )
        self.assertTrue(handler_err["retry_eligible"])
        self.assertEqual(handler_err["category"], OUTCOME_HANDLER_ERROR)
        self.assertNotIn("123456789012", handler_err["error_summary"])

        timeout = build_task_outcome(OUTCOME_TIMEOUT, 5000, "task-1", "attempt-3")
        self.assertTrue(timeout["retry_eligible"])

        size_err = build_task_outcome(OUTCOME_OUTPUT_LIMIT_EXCEEDED, 50, "task-1", "attempt-4")
        self.assertFalse(size_err["retry_eligible"])

    def test_heartbeat_keeper_renews_lease_in_background(self):
        lease = self.store.acquire_lease(self.job["id"], "worker-long", ttl_seconds=60)
        initial_hb = lease["heartbeat_at"]

        with HeartbeatKeeper(self.store, self.job["id"], lease["token"], interval_seconds=0.03, ttl_seconds=60) as keeper:
            for _ in range(25):
                if keeper.heartbeat_count > 0:
                    break
                time.sleep(0.02)
            self.assertGreater(keeper.heartbeat_count, 0)
            self.assertIsNotNone(keeper.last_heartbeat_at)

        # After exiting context manager, thread is stopped cleanly
        refreshed_lease = self.store.get_lease(self.job["id"])
        self.assertIsNotNone(refreshed_lease)
        self.assertGreaterEqual(refreshed_lease["heartbeat_at"], initial_hb)
        self.assertFalse(keeper._thread.is_alive())

    def test_heartbeat_keeper_handles_revoked_lease_gracefully(self):
        lease = self.store.acquire_lease(self.job["id"], "worker-doomed", ttl_seconds=60)

        with HeartbeatKeeper(self.store, self.job["id"], lease["token"], interval_seconds=0.03, ttl_seconds=60) as keeper:
            self.store.release_lease(self.job["id"], lease["token"])
            for _ in range(25):
                if keeper.last_error is not None:
                    break
                time.sleep(0.02)
            self.assertIsNotNone(keeper.last_error)

    def test_execution_controller_captures_structured_outcome(self):
        lease = self.store.acquire_lease(self.job["id"], "worker-exec", ttl_seconds=60)
        controller = ExecutionController(self.store)

        def slow_handler(payload):
            time.sleep(payload.get("input", {}).get("wait", 0.05))
            return {"done": True}

        def failing_handler(payload):
            raise RuntimeError("Operation failed with secret_key=secret999")

        controller.register("slow_task", slow_handler)
        controller.register("failing_task", failing_handler)

        # Run slow task (task-1-slow) with heartbeat enabled
        res1 = controller.run_next(
            self.job["id"],
            lease["token"],
            enable_heartbeat=True,
            heartbeat_interval=0.03,
        )
        self.assertEqual(res1["status"], "TASK_SUCCEEDED")
        self.assertIn("outcome", res1)
        self.assertEqual(res1["outcome"]["category"], OUTCOME_SUCCESS)
        self.assertGreaterEqual(res1["outcome"]["duration_ms"], 50)
        self.assertFalse(res1["outcome"]["retry_eligible"])

        # Run failing task
        res2 = controller.run_next(self.job["id"], lease["token"])
        self.assertEqual(res2["status"], "TASK_FAILED")
        self.assertIn("outcome", res2)
        self.assertEqual(res2["outcome"]["category"], OUTCOME_HANDLER_ERROR)
        self.assertTrue(res2["outcome"]["retry_eligible"])
        self.assertNotIn("secret999", res2["outcome"]["error_summary"])


if __name__ == "__main__":
    unittest.main()

