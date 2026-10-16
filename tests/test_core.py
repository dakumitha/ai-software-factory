import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from software_factory.core import ApiHandler, Store, ValidationError, ready_tasks, validate_task_graph
from software_factory.specs import SpecStore, build_plan


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


class SpecTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / "factory.sqlite3")
        self.project = self.store.create_project("Spec demo", "Build a small app")
        self.specs = SpecStore(self.store)
        self.spec = {"title": "Task tracker", "goal": "Track tasks and completion",
            "requirements": [
                {"id": "REQ-1", "description": "Create tasks", "acceptance_criteria": ["A task can be created with a title"]},
                {"id": "REQ-2", "description": "Complete tasks", "acceptance_criteria": ["A task can be marked complete"]}],
            "open_questions": []}

    def tearDown(self):
        self.tmp.cleanup()

    def test_spec_versions_are_immutable_and_increment(self):
        first = self.specs.save(self.project["id"], self.spec)
        second = self.specs.save(self.project["id"], {**self.spec, "goal": "Track and finish tasks"})
        self.assertEqual((first["version"], second["version"]), (1, 2))
        self.assertEqual(self.specs.get(first["id"])["spec"]["goal"], self.spec["goal"])

    def test_open_questions_block_approval(self):
        item = self.specs.save(self.project["id"], {**self.spec, "open_questions": ["Which login provider?"]})
        with self.assertRaises(ValidationError):
            self.specs.approve(item["id"])

    def test_approval_is_audited(self):
        item = self.specs.save(self.project["id"], self.spec)
        self.assertEqual(self.specs.approve(item["id"])["status"], "APPROVED")
        self.assertEqual(self.specs.events(item["id"])[0]["kind"], "spec.approved")

    def test_requirement_ids_must_be_unique_and_criteria_present(self):
        duplicate = {**self.spec, "requirements": [self.spec["requirements"][0], self.spec["requirements"][0]]}
        with self.assertRaises(ValidationError):
            self.specs.save(self.project["id"], duplicate)
        no_criteria = {**self.spec, "requirements": [{"id": "REQ-3", "description": "Something", "acceptance_criteria": []}]}
        with self.assertRaises(ValidationError):
            self.specs.save(self.project["id"], no_criteria)

    def test_plan_is_traceable_and_dependency_valid(self):
        plan = build_plan(self.spec)
        validate_task_graph(plan)
        self.assertEqual(plan[-1]["id"], "integration-verification")
        self.assertIn("REQ-1", plan[-1]["requirement_ids"])


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        ApiHandler.store = Store(Path(self.tmp.name) / "factory.sqlite3")
        ApiHandler.specs = SpecStore(ApiHandler.store)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), ApiHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.tmp.cleanup()

    def request(self, path, body=None):
        data = None if body is None else json.dumps(body).encode()
        req = Request(self.base + path, data=data, headers={"Content-Type": "application/json"})
        try:
            with urlopen(req, timeout=2) as response:
                return response.status, json.loads(response.read())
        except HTTPError as exc:
            return exc.code, json.loads(exc.read())

    def test_health_and_project_creation(self):
        status, health = self.request("/health")
        self.assertEqual(status, 200)
        self.assertTrue(health["ok"])
        status, project = self.request("/projects", {"name": "API Demo", "idea": "A small app"})
        self.assertEqual(status, 201)
        self.assertTrue(project["id"].startswith("prj_"))

    def test_spec_api_requires_approval_before_plan(self):
        _, project = self.request("/projects", {"name": "API Demo", "idea": "A small app"})
        spec_body = {"title": "Demo", "goal": "Demo goal",
            "requirements": [{"id": "R1", "description": "Create record", "acceptance_criteria": ["A record can be created"]}],
            "open_questions": []}
        status, spec = self.request(f"/projects/{project['id']}/specifications", spec_body)
        self.assertEqual(status, 201)
        status, error = self.request(f"/specifications/{spec['id']}/plan", {})
        self.assertEqual(status, 400)
        self.assertIn("Approve", error["error"])
        status, approved = self.request(f"/specifications/{spec['id']}/approve", {})
        self.assertEqual(status, 200)
        self.assertEqual(approved["status"], "APPROVED")
        status, plan = self.request(f"/specifications/{spec['id']}/plan", {})
        self.assertEqual(status, 200)
        self.assertEqual(plan["tasks"][-1]["id"], "integration-verification")


if __name__ == "__main__":
    unittest.main()
