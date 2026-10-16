import tempfile
import unittest
from pathlib import Path

from software_factory.core import Store, ValidationError, ready_tasks, validate_task_graph


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / "factory.sqlite3")
        self.project = self.store.create_project("Demo", "Build a small task tracker")

    def tearDown(self):
        self.tmp.cleanup()

    def test_project_and_job_survive_store_reopen(self):
        job = self.store.create_job(self.project["id"], spec={"goal": "demo"})
        reopened = Store(Path(self.tmp.name) / "factory.sqlite3")
        self.assertEqual(reopened.get_job(job["id"])["spec"]["goal"], "demo")
        self.assertEqual(reopened.get_job(job["id"])["state"], "DRAFT")

    def test_state_transition_is_logged_and_invalid_transition_rejected(self):
        job = self.store.create_job(self.project["id"])
        self.store.transition(job["id"], "NEEDS_CLARIFICATION", reason="Idea incomplete")
        self.assertEqual(self.store.get_job(job["id"])["state"], "NEEDS_CLARIFICATION")
        self.assertEqual(self.store.events(job["id"])[-1]["payload"]["to"], "NEEDS_CLARIFICATION")
        with self.assertRaises(ValidationError):
            self.store.transition(job["id"], "RELEASED")

    def test_release_cannot_be_forced(self):
        job = self.store.create_job(self.project["id"])
        with self.assertRaises(ValidationError):
            self.store.transition(job["id"], "RELEASED")

    def test_task_graph_checks_unknown_dependency_and_cycle(self):
        with self.assertRaises(ValidationError):
            validate_task_graph([{"id": "a", "title": "A", "depends_on": ["missing"]}])
        with self.assertRaises(ValidationError):
            validate_task_graph([
                {"id": "a", "title": "A", "depends_on": ["b"]},
                {"id": "b", "title": "B", "depends_on": ["a"]},
            ])

    def test_ready_tasks_respect_dependencies_and_requirement_traceability(self):
        tasks = validate_task_graph([
            {"id": "spec", "title": "Create spec", "requirement_ids": ["SF-REQ-002"]},
            {"id": "build", "title": "Build app", "requirement_ids": ["SF-REQ-008"], "depends_on": ["spec"]},
        ])
        self.assertEqual([t["id"] for t in ready_tasks(tasks)], ["spec"])
        self.assertEqual([t["id"] for t in ready_tasks(tasks, {"spec"})], ["build"])

    def test_missing_project_rejected(self):
        with self.assertRaises(ValidationError):
            self.store.create_job("does-not-exist")


if __name__ == "__main__":
    unittest.main()
