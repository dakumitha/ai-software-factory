"""Regression tests for the bounded create → verify → evidence workflow."""
import json
import tempfile
import unittest
from pathlib import Path

from software_factory.artifact_workflow import create_and_verify_artifact
from software_factory.artifacts import ArtifactError


class ArtifactWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tmp.name) / "workspace"

    def tearDown(self):
        self.tmp.cleanup()

    def test_creates_artifact_and_persists_independent_verification_evidence(self):
        result = create_and_verify_artifact(
            self.workspace,
            "output/result.json",
            '{"ready": true}\n',
            require_json=True,
        )
        self.assertEqual(result["status"], "PASSED")
        self.assertEqual(result["next_state"], "REVIEW_REQUIRED")
        self.assertFalse(result["release_performed"])
        self.assertEqual(result["verification"]["artifact_path"], "output/result.json")

        evidence = self.workspace / "evidence/verification-report.json"
        saved_report = json.loads(evidence.read_text(encoding="utf-8"))
        self.assertEqual(saved_report["status"], "PASSED")
        self.assertEqual(saved_report["sha256"], result["artifact"]["sha256"])

    def test_does_not_overwrite_artifact_or_evidence_on_repeat(self):
        create_and_verify_artifact(self.workspace, "output.txt", "first")
        with self.assertRaises(ArtifactError):
            create_and_verify_artifact(self.workspace, "output.txt", "second")
        self.assertEqual((self.workspace / "output.txt").read_text(), "first")

    def test_invalid_json_is_recorded_as_failed_and_not_released(self):
        result = create_and_verify_artifact(
            self.workspace, "result.json", "{not-json", require_json=True
        )
        self.assertEqual(result["status"], "FAILED")
        self.assertEqual(result["next_state"], "REVIEW_REQUIRED")
        self.assertFalse(result["release_performed"])


if __name__ == "__main__":
    unittest.main()
