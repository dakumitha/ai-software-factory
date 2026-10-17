"""Unit and integration tests for deterministic worker recovery handling."""
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from software_factory.core import Store, ValidationError
from software_factory.recovery import (
    LEASE_ACTIVE_VALID,
    LEASE_EXPIRED,
    LEASE_HEARTBEAT_OVERDUE,
    LEASE_MISSING,
    REC_ALL_TASKS_COMPLETE,
    REC_EXCEEDED_MAX_RETRIES,
    REC_NO_RECOVERY_NEEDED,
    REC_OPERATOR_REVIEW_REQUIRED,
    REC_RESUME_FROM_CHECKPOINT,
    REC_RETRY_TASK,
    RecoveryService,
    classify_lease_state,
    evaluate_job_recovery,
)


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "recovery_test.sqlite3"
        self.store = Store(self.db_path)
        self.recovery = RecoveryService(self.store)

        self.project = self.store.create_project("Recovery Demo", "Test crash recovery")
        self.tasks = [
            {"id": "task-1", "title": "First Step", "input": {"step": 1}},
            {"id": "task-2", "title": "Second Step", "input": {"step": 2}, "dependencies": ["task-1"]},
        ]
        self.job = self.store.create_job(self.project["id"], tasks=self.tasks)
        # Advance job to RUNNING
        for state in ["NEEDS_CLARIFICATION", "SPEC_READY", "PLAN_READY", "AWAITING_APPROVAL", "QUEUED", "RUNNING"]:
            self.store.transition(self.job["id"], state)

    def tearDown(self):
        self.tmp.cleanup()

    def test_classify_lease_state(self):
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat(timespec="seconds")

        # Missing lease
        self.assertEqual(classify_lease_state(None, now=now_iso), LEASE_MISSING)

        # Expired lease
        expired_ts = (now - timedelta(seconds=10)).isoformat(timespec="seconds")
        self.assertEqual(
            classify_lease_state({"expires_at": expired_ts}, now=now_iso),
            LEASE_EXPIRED,
        )

        # Active valid lease
        fresh_hb = (now - timedelta(seconds=10)).isoformat(timespec="seconds")
        valid_exp = (now + timedelta(seconds=60)).isoformat(timespec="seconds")
        self.assertEqual(
            classify_lease_state(
                {"expires_at": valid_exp, "heartbeat_at": fresh_hb},
                now=now_iso,
                heartbeat_grace_seconds=120,
            ),
            LEASE_ACTIVE_VALID,
        )

        # Heartbeat overdue
        stale_hb = (now - timedelta(seconds=200)).isoformat(timespec="seconds")
        self.assertEqual(
            classify_lease_state(
                {"expires_at": valid_exp, "heartbeat_at": stale_hb},
                now=now_iso,
                heartbeat_grace_seconds=120,
            ),
            LEASE_HEARTBEAT_OVERDUE,
        )

    def test_evaluate_healthy_active_job_requires_no_recovery(self):
        lease = self.store.acquire_lease(self.job["id"], "worker-alpha", ttl_seconds=60)
        evaluation = self.recovery.evaluate_job(self.job["id"])

        self.assertEqual(evaluation["lease_state"], LEASE_ACTIVE_VALID)
        self.assertEqual(evaluation["lease_owner"], "worker-alpha")
        self.assertEqual(evaluation["recommendation"], REC_NO_RECOVERY_NEEDED)
        self.assertFalse(evaluation["safe_to_reacquire_lease"])

    def test_evaluate_expired_lease_with_started_attempt_requires_operator_review(self):
        # Worker acquires lease and starts task-1
        lease = self.store.acquire_lease(self.job["id"], "worker-alpha", ttl_seconds=60)
        attempt = self.store.start_task_attempt(
            self.job["id"], "task-1", lease["token"], "key-1", {"step": 1}
        )
        self.assertEqual(attempt["status"], "STARTED")

        # Simulate time passing beyond lease expiry
        future_now = (datetime.now(timezone.utc) + timedelta(seconds=100)).isoformat(timespec="seconds")
        evaluation = self.recovery.evaluate_job(self.job["id"], now=future_now)

        self.assertEqual(evaluation["lease_state"], LEASE_EXPIRED)
        self.assertEqual(evaluation["recommendation"], REC_OPERATOR_REVIEW_REQUIRED)
        self.assertFalse(evaluation["safe_to_reacquire_lease"])
        self.assertIsNotNone(evaluation["in_flight_attempt"])
        self.assertEqual(evaluation["in_flight_attempt"]["id"], attempt["id"])
        self.assertIn("STARTED", evaluation["reason"])

    def test_evaluate_expired_lease_with_clean_checkpoint_can_resume(self):
        # Task 1 was completed cleanly in checkpoint before worker died
        self.store.save_checkpoint(self.job["id"], {"completed_task_ids": ["task-1"]})
        lease = self.store.acquire_lease(self.job["id"], "worker-alpha", ttl_seconds=60)

        # Simulate lease expiry
        future_now = (datetime.now(timezone.utc) + timedelta(seconds=100)).isoformat(timespec="seconds")
        evaluation = self.recovery.evaluate_job(self.job["id"], now=future_now)

        self.assertEqual(evaluation["lease_state"], LEASE_EXPIRED)
        self.assertEqual(evaluation["recommendation"], REC_RESUME_FROM_CHECKPOINT)
        self.assertTrue(evaluation["safe_to_reacquire_lease"])
        self.assertEqual(evaluation["current_task_id"], "task-2")
        self.assertEqual(evaluation["completed_task_ids"], ["task-1"])

    def test_evaluate_bounded_retries(self):
        # Simulate a completed attempt that failed
        lease = self.store.acquire_lease(self.job["id"], "worker-alpha", ttl_seconds=60)
        attempt1 = self.store.start_task_attempt(
            self.job["id"], "task-1", lease["token"], "key-retry-1", {"step": 1}
        )
        self.store.finish_task_attempt(
            self.job["id"], attempt1["id"], lease["token"], "FAILED", error="Network timeout"
        )

        future_now = (datetime.now(timezone.utc) + timedelta(seconds=100)).isoformat(timespec="seconds")
        # Attempt count is 1 of 3: eligible for retry
        eval1 = self.recovery.evaluate_job(self.job["id"], now=future_now, max_retries=3)
        self.assertEqual(eval1["recommendation"], REC_RETRY_TASK)
        self.assertEqual(eval1["retry_count"], 1)

        # Simulate 2 more failures
        self.store.release_lease(self.job["id"], lease["token"])
        lease2 = self.store.acquire_lease(self.job["id"], "worker-beta", ttl_seconds=60)
        attempt2 = self.store.start_task_attempt(
            self.job["id"], "task-1", lease2["token"], "key-retry-2", {"step": 1}
        )
        self.store.finish_task_attempt(
            self.job["id"], attempt2["id"], lease2["token"], "FAILED", error="DNS failure"
        )

        self.store.release_lease(self.job["id"], lease2["token"])
        lease3 = self.store.acquire_lease(self.job["id"], "worker-gamma", ttl_seconds=60)
        attempt3 = self.store.start_task_attempt(
            self.job["id"], "task-1", lease3["token"], "key-retry-3", {"step": 1}
        )
        self.store.finish_task_attempt(
            self.job["id"], attempt3["id"], lease3["token"], "FAILED", error="Connection refused"
        )

        # Total 3 failures: exceeds max retries limit
        future_now3 = (datetime.now(timezone.utc) + timedelta(seconds=150)).isoformat(timespec="seconds")
        eval3 = self.recovery.evaluate_job(self.job["id"], now=future_now3, max_retries=3)
        self.assertEqual(eval3["recommendation"], REC_EXCEEDED_MAX_RETRIES)
        self.assertFalse(eval3["safe_to_reacquire_lease"])

    def test_reconcile_expired_lease_with_started_attempt(self):
        lease = self.store.acquire_lease(self.job["id"], "worker-alpha", ttl_seconds=60)
        attempt = self.store.start_task_attempt(
            self.job["id"], "task-1", lease["token"], "key-rec-1", {"step": 1}
        )

        # Expire the lease
        future_now = (datetime.now(timezone.utc) + timedelta(seconds=100)).isoformat(timespec="seconds")

        reconcile_result = self.recovery.reconcile_job(self.job["id"], now=future_now)

        self.assertIn(f"marked_attempt_{attempt['id']}_uncertain", reconcile_result["actions_applied"])
        self.assertIn("expired_lease_revoked", reconcile_result["actions_applied"])

        # Check attempt in store
        persisted_attempt = self.store.get_task_attempt(self.job["id"], attempt["id"])
        self.assertEqual(persisted_attempt["status"], "UNCERTAIN")
        self.assertIn("interrupted", persisted_attempt["error_text"])

        # Check lease in store is revoked
        self.assertIsNone(self.store.get_lease(self.job["id"]))

        # Verify audit events recorded
        events = self.store.events(self.job["id"])
        event_kinds = [e["kind"] for e in events]
        self.assertIn("task.attempt_interrupted", event_kinds)
        self.assertIn("job.lease_revoked", event_kinds)
        self.assertIn("job.recovery_reconciled", event_kinds)

    def test_cannot_revoke_active_unexpired_lease(self):
        self.store.acquire_lease(self.job["id"], "worker-alpha", ttl_seconds=600)
        with self.assertRaises(ValidationError) as ctx:
            self.store.revoke_expired_lease(self.job["id"])
        self.assertIn("active, unexpired lease", str(ctx.exception))

    def test_inventory_stale_work(self):
        # Job 1 is RUNNING with an expired lease
        self.store.acquire_lease(self.job["id"], "worker-1", ttl_seconds=10)
        future_now = (datetime.now(timezone.utc) + timedelta(seconds=20)).isoformat(timespec="seconds")

        # Job 2 is created in DRAFT state
        draft_job = self.store.create_job(self.project["id"], tasks=[])

        inventory = self.recovery.inventory_stale_work(now=future_now)
        job_ids = [item["job_id"] for item in inventory]

        self.assertIn(self.job["id"], job_ids)
        self.assertNotIn(draft_job["id"], job_ids)

    def test_recovery_never_transitions_to_released(self):
        # Recovery must never directly claim RELEASED state
        evaluation = self.recovery.evaluate_job(self.job["id"])
        self.assertNotEqual(evaluation.get("job_state"), "RELEASED")
        reconciled = self.recovery.reconcile_job(self.job["id"])
        refreshed_job = self.store.get_job(self.job["id"])
        self.assertNotEqual(refreshed_job["state"], "RELEASED")


if __name__ == "__main__":
    unittest.main()

