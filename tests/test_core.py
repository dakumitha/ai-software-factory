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

    def test_schema_migrations_are_recorded_and_repeatable(self):
        self.assertEqual(self.store.schema_version(), 3)
        reopened = Store(Path(self.tmp.name) / "factory.sqlite3")
        self.assertEqual(reopened.schema_version(), 3)
        with reopened.connect() as db:
            versions = [row["version"] for row in db.execute(
                "SELECT version FROM schema_migrations ORDER BY version"
            )]
            indexes = {row["name"] for row in db.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            )}
        self.assertEqual(versions, [1, 2, 3])
        self.assertIn("idx_jobs_state_updated_at", indexes)
        self.assertIn("idx_events_job_id_id", indexes)
        self.assertIn("idx_job_leases_expires_at", indexes)

    def test_legacy_database_is_migrated_without_losing_records(self):
        import sqlite3
        legacy_path = Path(self.tmp.name) / "legacy.sqlite3"
        with sqlite3.connect(legacy_path) as db:
            db.executescript("""
                CREATE TABLE projects (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL, idea TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE jobs (
                    id TEXT PRIMARY KEY, project_id TEXT NOT NULL, state TEXT NOT NULL,
                    spec_json TEXT NOT NULL, tasks_json TEXT NOT NULL, budget_json TEXT NOT NULL,
                    checkpoint_json TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    FOREIGN KEY(project_id) REFERENCES projects(id)
                );
                CREATE TABLE events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, job_id TEXT NOT NULL, at TEXT NOT NULL,
                    actor TEXT NOT NULL, kind TEXT NOT NULL, payload_json TEXT NOT NULL,
                    FOREIGN KEY(job_id) REFERENCES jobs(id)
                );
                INSERT INTO projects VALUES ('prj_legacy', 'Legacy project', 'Preserve me', '2026-01-01T00:00:00+00:00');
            """)
        migrated = Store(legacy_path)
        self.assertEqual(migrated.schema_version(), 3)
        self.assertEqual(migrated.get_project("prj_legacy")["name"], "Legacy project")
        with migrated.connect() as db:
            self.assertEqual(db.execute(
                "SELECT COUNT(*) FROM projects WHERE id='prj_legacy'"
            ).fetchone()[0], 1)

    def test_worker_lease_excludes_live_job_from_recovery_inventory(self):
        job = self.store.create_job(self.project["id"])
        for target in ["NEEDS_CLARIFICATION", "SPEC_READY", "PLAN_READY",
                       "AWAITING_APPROVAL", "QUEUED", "RUNNING"]:
            self.store.transition(job["id"], target)
        lease = self.store.acquire_lease(job["id"], "worker-1", ttl_seconds=60)
        self.assertNotIn(job["id"], [item["job_id"] for item in self.store.list_interrupted_jobs()])
        heartbeat = self.store.heartbeat_lease(job["id"], lease["token"], ttl_seconds=60)
        self.assertEqual(heartbeat["owner_id"], "worker-1")
        with self.assertRaises(ValidationError):
            self.store.heartbeat_lease(job["id"], "wrong-token")
        self.store.release_lease(job["id"], lease["token"])
        candidates = self.store.list_interrupted_jobs()
        self.assertEqual(candidates[0]["job_id"], job["id"])
        self.assertEqual(candidates[0]["lease_status"], "missing")

    def test_worker_lease_requires_active_job_and_valid_ttl(self):
        job = self.store.create_job(self.project["id"])
        with self.assertRaises(ValidationError):
            self.store.acquire_lease(job["id"], "worker-1")
        with self.assertRaises(ValidationError):
            self.store.acquire_lease(job["id"], "worker-1", ttl_seconds=2)

    def test_interrupted_job_inventory_is_read_only_and_excludes_inactive_jobs(self):
        running = self.store.create_job(self.project["id"], tasks=[{"id": "build", "title": "Build"}])
        for target in ["NEEDS_CLARIFICATION", "SPEC_READY", "PLAN_READY",
                       "AWAITING_APPROVAL", "QUEUED", "RUNNING"]:
            self.store.transition(running["id"], target)
        self.store.save_checkpoint(running["id"], {
            "current_task_id": "build", "completed_task_ids": []
        })
        inactive = self.store.create_job(self.project["id"])
        before = self.store.get_job(running["id"])["state"]
        candidates = self.store.list_interrupted_jobs()
        self.assertEqual([item["job_id"] for item in candidates], [running["id"]])
        self.assertEqual(candidates[0]["recovery_status"], "operator_review_required")
        self.assertEqual(candidates[0]["current_task_id"], "build")
        self.assertEqual(self.store.get_job(running["id"])["state"], before)
        self.assertEqual(self.store.get_job(inactive["id"])["state"], "DRAFT")

    def test_project_and_job_survive_store_reopen(self):
        job = self.store.create_job(self.project["id"], spec={"goal": "demo"})
        reopened = Store(Path(self.tmp.name) / "factory.sqlite3")
        self.assertEqual(reopened.get_job(job["id"])["spec"]["goal"], "demo")
        self.assertEqual(reopened.get_job(job["id"])["state"], "DRAFT")

    def test_checkpoint_survives_store_reopen_and_records_audit_event(self):
        job = self.store.create_job(self.project["id"], tasks=[
            {"id": "design", "title": "Design"},
            {"id": "build", "title": "Build", "depends_on": ["design"]},
        ])
        saved = self.store.save_checkpoint(job["id"], {
            "stage": "building", "current_task_id": "build",
            "completed_task_ids": ["design"], "resume_count": 1,
        })
        reopened = Store(Path(self.tmp.name) / "factory.sqlite3")
        recovered = reopened.get_job(job["id"])
        self.assertEqual(recovered["checkpoint"], saved["checkpoint"])
        self.assertEqual(recovered["checkpoint"]["completed_task_ids"], ["design"])
        self.assertEqual(reopened.events(job["id"])[-1]["kind"], "job.checkpoint_saved")

    def test_checkpoint_save_is_idempotent_for_identical_state(self):
        job = self.store.create_job(self.project["id"], tasks=[{"id": "one", "title": "One"}])
        checkpoint = {"stage": "running", "current_task_id": "one", "completed_task_ids": []}
        self.store.save_checkpoint(job["id"], checkpoint)
        count = len(self.store.events(job["id"]))
        self.store.save_checkpoint(job["id"], checkpoint)
        self.assertEqual(len(self.store.events(job["id"])), count)

    def test_checkpoint_rejects_unknown_or_regressed_completed_tasks(self):
        job = self.store.create_job(self.project["id"], tasks=[{"id": "one", "title": "One"}])
        with self.assertRaises(ValidationError):
            self.store.save_checkpoint(job["id"], {"completed_task_ids": ["unknown"]})
        self.store.save_checkpoint(job["id"], {"completed_task_ids": ["one"]})
        with self.assertRaises(ValidationError):
            self.store.save_checkpoint(job["id"], {"completed_task_ids": []})

    def test_database_backup_restores_project_job_checkpoint_and_events(self):
        job = self.store.create_job(self.project["id"], tasks=[{"id": "one", "title": "One"}])
        self.store.save_checkpoint(job["id"], {
            "stage": "building", "current_task_id": "one", "completed_task_ids": [],
        })
        backup_path = Path(self.tmp.name) / "backup" / "factory-backup.sqlite3"
        self.assertEqual(self.store.backup_to(backup_path), backup_path)
        restored = Store(backup_path)
        self.assertEqual(restored.get_project(self.project["id"])["name"], "Demo")
        self.assertEqual(restored.get_job(job["id"])["checkpoint"]["stage"], "building")
        self.assertEqual(restored.events(job["id"])[-1]["kind"], "job.checkpoint_saved")

    def test_database_backup_rejects_live_database_as_destination(self):
        with self.assertRaises(ValidationError):
            self.store.backup_to(Path(self.store.path))

    def test_checkpoint_rejects_unknown_current_task(self):
        job = self.store.create_job(self.project["id"], tasks=[{"id": "one", "title": "One"}])
        with self.assertRaises(ValidationError):
            self.store.save_checkpoint(job["id"], {"current_task_id": "missing"})

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

    def test_concurrent_spec_writes_allocate_unique_versions(self):
        barrier = threading.Barrier(6)
        results = []
        failures = []
        lock = threading.Lock()

        def save_revision(index):
            try:
                barrier.wait(timeout=3)
                item = self.specs.save(self.project["id"], {**self.spec, "goal": f"Revision {index}"})
                with lock:
                    results.append(item["version"])
            except Exception as exc:
                with lock:
                    failures.append(exc)

        workers = [threading.Thread(target=save_revision, args=(i,)) for i in range(6)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(timeout=8)
        self.assertEqual(failures, [])
        self.assertEqual(sorted(results), [1, 2, 3, 4, 5, 6])

    def test_invalid_requirement_priority_is_rejected(self):
        invalid = {**self.spec, "requirements": [
            {**self.spec["requirements"][0], "priority": "urgent"}
        ]}
        with self.assertRaises(ValidationError):
            self.specs.save(self.project["id"], invalid)

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

    def test_malformed_json_returns_controlled_client_error(self):
        req = Request(self.base + "/projects", data=b"{broken", headers={"Content-Type": "application/json"})
        try:
            with urlopen(req, timeout=2) as response:
                self.fail(f"Expected 400, received {response.status}")
        except HTTPError as exc:
            self.assertEqual(exc.code, 400)
            self.assertIn("valid UTF-8 JSON", json.loads(exc.read())["error"])

    def test_spec_list_rejects_unknown_project(self):
        status, payload = self.request("/projects/missing-project/specifications")
        self.assertEqual(status, 404)
        self.assertIn("Project not found", payload["error"])

    def test_lease_api_acquire_heartbeat_and_release(self):
        _, project = self.request("/projects", {"name": "Lease API", "idea": "Track worker ownership"})
        _, job = self.request("/jobs", {"project_id": project["id"]})
        for target in ["NEEDS_CLARIFICATION", "SPEC_READY", "PLAN_READY",
                       "AWAITING_APPROVAL", "QUEUED", "RUNNING"]:
            status, result = self.request(f"/jobs/{job['id']}/transition", {"target": target})
            self.assertEqual(status, 200, result)
        status, lease = self.request(f"/jobs/{job['id']}/lease", {"owner_id": "api-worker", "ttl_seconds": 60})
        self.assertEqual(status, 201, lease)
        status, heartbeat = self.request(f"/jobs/{job['id']}/lease/heartbeat",
            {"token": lease["token"], "ttl_seconds": 60})
        self.assertEqual(status, 200, heartbeat)
        status, released = self.request(f"/jobs/{job['id']}/lease/release", {"token": lease["token"]})
        self.assertEqual(status, 200, released)
        self.assertTrue(released["released"])

    def test_interrupted_recovery_endpoint_lists_candidates_without_mutating_them(self):
        _, project = self.request("/projects", {"name": "Recovery API", "idea": "Inventory interrupted work"})
        _, job = self.request("/jobs", {"project_id": project["id"]})
        for target in ["NEEDS_CLARIFICATION", "SPEC_READY", "PLAN_READY",
                       "AWAITING_APPROVAL", "QUEUED", "RUNNING"]:
            status, result = self.request(f"/jobs/{job['id']}/transition", {"target": target})
            self.assertEqual(status, 200, result)
        status, result = self.request("/recovery/interrupted")
        self.assertEqual(status, 200)
        self.assertFalse(result["automatic_resume"])
        self.assertEqual(result["items"][0]["job_id"], job["id"])
        self.assertEqual(ApiHandler.store.get_job(job["id"])["state"], "RUNNING")

    def test_checkpoint_api_persists_task_progress(self):
        _, project = self.request("/projects", {"name": "Recovery API", "idea": "Test durable checkpoints"})
        _, job = self.request("/jobs", {"project_id": project["id"], "tasks": [
            {"id": "design", "title": "Design"},
            {"id": "build", "title": "Build", "depends_on": ["design"]},
        ]})
        status, updated = self.request(f"/jobs/{job['id']}/checkpoint", {
            "checkpoint": {"stage": "building", "current_task_id": "build",
                           "completed_task_ids": ["design"]}
        })
        self.assertEqual(status, 200, updated)
        self.assertEqual(updated["checkpoint"]["completed_task_ids"], ["design"])
        status, error = self.request(f"/jobs/{job['id']}/checkpoint", {
            "checkpoint": {"completed_task_ids": ["not-a-task"]}
        })
        self.assertEqual(status, 400)
        self.assertIn("unknown completed tasks", error["error"])

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
        self.assertEqual(status, 200, plan)
        self.assertEqual(plan["tasks"][-1]["id"], "integration-verification")


if __name__ == "__main__":
    unittest.main()
