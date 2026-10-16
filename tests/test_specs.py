import tempfile
import unittest
from pathlib import Path

from software_factory.core import Store, ValidationError, validate_task_graph
from software_factory.specs import SpecStore, build_plan


class SpecTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / "factory.sqlite3")
        self.project = self.store.create_project("Spec demo", "Build a small app")
        self.specs = SpecStore(self.store)
        self.spec = {
            "title": "Task tracker",
            "goal": "Track tasks and their completion",
            "requirements": [
                {"id": "REQ-1", "description": "Create tasks",
                 "acceptance_criteria": ["A task can be created with a title"]},
                {"id": "REQ-2", "description": "Complete tasks",
                 "acceptance_criteria": ["A task can be marked complete"]},
            ],
            "open_questions": [],
        }

    def tearDown(self):
        self.tmp.cleanup()

    def test_spec_versions_are_immutable_and_increment(self):
        first = self.specs.save(self.project["id"], self.spec)
        changed = {**self.spec, "goal": "Track and finish tasks"}
        second = self.specs.save(self.project["id"], changed)
        self.assertEqual((first["version"], second["version"]), (1, 2))
        self.assertEqual(self.specs.get(first["id"])["spec"]["goal"], self.spec["goal"])

    def test_open_questions_block_approval(self):
        spec = self.specs.save(self.project["id"], {**self.spec, "open_questions": ["Which login provider?"]})
        with self.assertRaises(ValidationError):
            self.specs.approve(spec["id"])

    def test_approval_is_audited(self):
        spec = self.specs.save(self.project["id"], self.spec)
        approved = self.specs.approve(spec["id"])
        self.assertEqual(approved["status"], "APPROVED")
        self.assertEqual(self.specs.events(spec["id"])[0]["kind"], "spec.approved")

    def test_requirement_ids_must_be_unique_and_criteria_present(self):
        duplicate = {**self.spec, "requirements": [
            self.spec["requirements"][0], self.spec["requirements"][0]
        ]}
        with self.assertRaises(ValidationError):
            self.specs.save(self.project["id"], duplicate)
        no_criteria = {**self.spec, "requirements": [
            {"id": "REQ-3", "description": "Something", "acceptance_criteria": []}
        ]}
        with self.assertRaises(ValidationError):
            self.specs.save(self.project["id"], no_criteria)

    def test_plan_is_traceable_and_dependency_valid(self):
        plan = build_plan(self.spec)
        validate_task_graph(plan)
        self.assertEqual(plan[-1]["id"], "integration-verification")
        self.assertIn("REQ-1", plan[-1]["requirement_ids"])


if __name__ == "__main__":
    unittest.main()
