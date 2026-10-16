"""Tests for the allowlisted artifact integrity task handler."""
import tempfile
import unittest
from pathlib import Path
from software_factory.artifact_task import ArtifactTaskError, handle_artifact_integrity_task

class ArtifactTaskTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
    def tearDown(self):
        self.tmp.cleanup()
    def test_allowlisted_task_saves_evidence_and_requires_review(self):
        root = Path(self.tmp.name) / "workspace"
        result = handle_artifact_integrity_task(root, {"kind": "artifact_integrity", "path": "out.json", "content": "{}", "require_json": True})
        self.assertEqual(result["status"], "PASSED")
        self.assertEqual(result["next_state"], "REVIEW_REQUIRED")
        self.assertFalse(result["release_performed"])
        self.assertTrue((root / "evidence/verification-report.json").is_file())
    def test_unknown_kind_rejected_before_workspace_creation(self):
        root = Path(self.tmp.name) / "workspace"
        with self.assertRaises(ArtifactTaskError):
            handle_artifact_integrity_task(root, {"kind": "shell", "command": "echo unsafe"})
        self.assertFalse(root.exists())
    def test_invalid_option_type_rejected(self):
        with self.assertRaises(ArtifactTaskError):
            handle_artifact_integrity_task(Path(self.tmp.name) / "workspace", {"kind": "artifact_integrity", "path": "out.json", "content": "{}", "require_json": "yes"})

if __name__ == "__main__":
    unittest.main()
