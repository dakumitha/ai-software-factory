"""Tests for the end-to-end vertical slice delivery pipeline."""
import json
import tempfile
import unittest
from pathlib import Path

from software_factory.core import Store, ValidationError
from software_factory.pipeline import PipelineError, run_vertical_slice_pipeline
from software_factory.resilience import CIRCUIT_CLOSED


class VerticalSlicePipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.tmp.name)
        self.workspace = self.base_dir / "workspace"
        self.db_path = self.base_dir / "pipeline.sqlite3"
        self.store = Store(self.db_path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_end_to_end_vertical_slice_success(self):
        spec = {
            "title": "School Bus Transport Notification System",
            "goal": "Provide safe and verifiable ETA notifications for school buses.",
            "requirements": [
                {
                    "id": "REQ-TRANS-001",
                    "description": "Send student boarding notifications to parents",
                    "priority": "must",
                    "acceptance_criteria": ["Notification contains timestamp and stop location."],
                },
                {
                    "id": "REQ-TRANS-002",
                    "description": "Maintain driver route checkpoint integrity",
                    "priority": "must",
                    "acceptance_criteria": ["Checkpoints are immutably signed and sequenced."],
                },
            ],
            "open_questions": [],
            "assumptions": ["All communication happens through verified local mock adapters."],
            "constraints": ["Zero paid cloud spend", "Strict review-gated delivery"],
        }

        result = run_vertical_slice_pipeline(
            self.workspace,
            self.store,
            spec,
            project_name="School Transport Platform",
            project_goal=spec["goal"],
            enable_heartbeat=True,
            heartbeat_interval=0.03,
        )

        self.assertEqual(result["status"], "COMPLETED_REVIEW_REQUIRED")
        self.assertEqual(result["final_job_state"], "REVIEW_REQUIRED")
        self.assertFalse(result["release_performed"])
        self.assertEqual(result["planned_tasks_count"], 4)  # foundation, 2 reqs, integration-verification
        self.assertEqual(len(result["completed_task_ids"]), 4)
        self.assertEqual(result["artifacts_verified_count"], 4)
        self.assertEqual(result["circuit_breaker_status"]["state"], CIRCUIT_CLOSED)

        # Verify on-disk artifacts and verification reports
        for task_id in result["completed_task_ids"]:
            art_file = self.workspace / "artifacts" / f"{task_id}.json"
            ev_file = self.workspace / "evidence" / f"{task_id}-report.json"
            self.assertTrue(art_file.exists(), f"Artifact missing: {art_file}")
            self.assertTrue(ev_file.exists(), f"Evidence report missing: {ev_file}")

            # Verify content is valid JSON
            art_data = json.loads(art_file.read_text(encoding="utf-8"))
            self.assertEqual(art_data["task_id"], task_id)
            self.assertTrue(art_data["verified"])

            ev_data = json.loads(ev_file.read_text(encoding="utf-8"))
            self.assertEqual(ev_data["status"], "PASSED")

    def test_pipeline_rejects_spec_with_open_questions(self):
        spec = {
            "title": "Unclear Transport System",
            "goal": "Vague goals",
            "requirements": [
                {
                    "id": "REQ-UNCLEAR-001",
                    "description": "Something vaguely defined",
                    "priority": "must",
                    "acceptance_criteria": ["Something happens."],
                }
            ],
            "open_questions": ["What is the target notification channel?"],
            "assumptions": [],
            "constraints": [],
        }

        with self.assertRaises(ValidationError) as ctx:
            run_vertical_slice_pipeline(self.workspace, self.store, spec)

        self.assertIn("Resolve open questions before approving", str(ctx.exception))

    def test_pipeline_never_transitions_to_released(self):
        spec = {
            "title": "Safety Gate Test",
            "goal": "Verify human gate invariant.",
            "requirements": [
                {
                    "id": "REQ-GATE-001",
                    "description": "Safe task",
                    "priority": "must",
                    "acceptance_criteria": ["Safety check passes."],
                }
            ],
            "open_questions": [],
            "assumptions": [],
            "constraints": [],
        }

        result = run_vertical_slice_pipeline(self.workspace, self.store, spec)
        self.assertNotEqual(result["final_job_state"], "RELEASED")
        self.assertNotEqual(result["final_job_state"], "RELEASE_READY")
        self.assertEqual(result["final_job_state"], "REVIEW_REQUIRED")
        self.assertFalse(result["release_performed"])

        # Inspect database job events to ensure RELEASED event never occurred
        job = self.store.get_job(result["job_id"])
        self.assertEqual(job["state"], "REVIEW_REQUIRED")
        events = self.store.events(result["job_id"])
        states = [e["payload"].get("to_state") for e in events if e["kind"] == "job.transition"]
        self.assertNotIn("RELEASED", states)
        self.assertNotIn("RELEASE_READY", states)


if __name__ == "__main__":
    unittest.main()

