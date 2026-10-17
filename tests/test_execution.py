import tempfile
import unittest
from pathlib import Path

from software_factory.core import Store
from software_factory.execution import ExecutionController


class ExecutionControllerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / "factory.sqlite3")
        self.project = self.store.create_project("Controller tests", "Exercise deterministic handlers")
        self.job = self.store.create_job(self.project["id"], spec={"goal": "test"}, tasks=[
            {"id": "first", "title": "First", "type": "echo", "input": {"value": "one"}},
            {"id": "second", "title": "Second", "type": "echo", "input": {"value": "two"}, "depends_on": ["first"]},
        ])
        for state in ("NEEDS_CLARIFICATION", "SPEC_READY", "PLAN_READY", "AWAITING_APPROVAL", "QUEUED", "RUNNING"):
            self.store.transition(self.job["id"], state)
        self.lease = self.store.acquire_lease(self.job["id"], "test-worker")
        self.controller = ExecutionController(self.store, {"echo": lambda payload: payload["input"]})

    def tearDown(self):
        self.tmp.cleanup()

    def test_runs_tasks_in_dependency_order_and_persists_checkpoints(self):
        first = self.controller.run_next(self.job["id"], self.lease["token"])
        self.assertEqual(first["status"], "TASK_SUCCEEDED")
        self.assertEqual(first["task_id"], "first")
        second = self.controller.run_next(self.job["id"], self.lease["token"])
        self.assertEqual(second["status"], "TASK_SUCCEEDED")
        self.assertEqual(second["task_id"], "second")
        self.assertEqual(second["completed_task_ids"], ["first", "second"])
        self.assertEqual(self.controller.run_next(self.job["id"], self.lease["token"])["status"], "ALL_COMPLETE")

    def test_missing_handler_does_not_create_attempt_or_execute_task(self):
        result = ExecutionController(self.store).run_next(self.job["id"], self.lease["token"])
        self.assertEqual(result["status"], "BLOCKED_HANDLER_MISSING")
        self.assertEqual(self.store.list_task_attempts(self.job["id"]), [])

    def test_handler_failure_is_recorded_and_does_not_mark_task_complete(self):
        def fail(_):
            raise RuntimeError("expected test failure")
        controller = ExecutionController(self.store, {"echo": fail})
        result = controller.run_next(self.job["id"], self.lease["token"])
        self.assertEqual(result["status"], "TASK_FAILED")
        self.assertEqual(self.store.list_task_attempts(self.job["id"])[0]["status"], "FAILED")
        self.assertEqual(self.store.get_job(self.job["id"])["checkpoint"].get("completed_task_ids", []), [])

    def test_handler_output_must_be_json_serializable(self):
        controller = ExecutionController(self.store, {"echo": lambda _: object()})
        result = controller.run_next(self.job["id"], self.lease["token"])
        self.assertEqual(result["status"], "TASK_FAILED")
        self.assertEqual(self.store.list_task_attempts(self.job["id"])[0]["status"], "FAILED")

    def test_duplicate_handler_registration_is_rejected(self):
        with self.assertRaises(ValueError):
            self.controller.register("echo", lambda _: None)

    def test_invalid_job_state_is_rejected(self):
        project = self.store.create_project("Draft", "No execution")
        draft = self.store.create_job(project["id"])
        with self.assertRaises(Exception):
            self.controller.run_next(draft["id"], "not-a-token")


if __name__ == "__main__":
    unittest.main()
