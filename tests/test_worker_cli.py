import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from software_factory.core import Store
from software_factory.worker_cli import main


class WorkerCliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.database = str(Path(self.tmp.name) / "factory.sqlite3")
        self.store = Store(self.database)
        self.project = self.store.create_project("CLI tests", "Inspect persisted jobs")
        self.job = self.store.create_job(
            self.project["id"],
            spec={"private_note": "must-not-appear-in-summary"},
            tasks=[{"id": "task-1", "title": "Example", "input": {"token": "never-print"}}],
        )

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self, *args):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = main(["--database", self.database, *args])
        return code, output.getvalue()

    def test_status_shows_summary_without_task_or_spec_payloads(self):
        code, output = self.run_cli("status", self.job["id"])
        self.assertEqual(code, 0)
        result = json.loads(output)
        self.assertEqual(result["job_id"], self.job["id"])
        self.assertEqual(result["state"], "DRAFT")
        self.assertEqual(result["task_count"], 1)
        self.assertEqual(result["completed_task_count"], 0)
        self.assertNotIn("must-not-appear-in-summary", output)
        self.assertNotIn("never-print", output)

    def test_list_can_filter_by_project(self):
        self.store.create_job(self.project["id"], tasks=[])
        code, output = self.run_cli("list", "--project-id", self.project["id"])
        self.assertEqual(code, 0)
        result = json.loads(output)
        self.assertEqual(result["count"], 2)
        self.assertTrue(all("task_count" in item for item in result["items"]))

    def test_unknown_job_returns_nonzero_and_structured_error(self):
        code, output = self.run_cli("status", "job-does-not-exist")
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(output)["error"], "Job not found")


if __name__ == "__main__":
    unittest.main()
