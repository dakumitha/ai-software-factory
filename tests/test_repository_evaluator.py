import json
import tempfile
import unittest
from pathlib import Path

from software_factory.repository_evaluator import evaluate_repository


class RepositoryEvaluatorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_empty_directory_is_review_required_and_low_score(self):
        report = evaluate_repository(self.root)
        self.assertEqual(report["adoption_status"], "REVIEW_REQUIRED")
        self.assertLess(report["score"], 45)
        self.assertEqual(report["assessment_mode"], "static_metadata_only")

    def test_detects_metadata_without_running_scripts(self):
        (self.root / "README.md").write_text("# Example", encoding="utf-8")
        (self.root / "LICENSE").write_text("MIT", encoding="utf-8")
        (self.root / "package.json").write_text(json.dumps({
            "name": "example", "scripts": {"postinstall": "echo should-not-run"}
        }), encoding="utf-8")
        (self.root / "package-lock.json").write_text("{}", encoding="utf-8")
        (self.root / ".github" / "workflows").mkdir(parents=True)
        (self.root / ".github" / "workflows" / "ci.yml").write_text("name: CI", encoding="utf-8")
        (self.root / "tests").mkdir()
        report = evaluate_repository(self.root)
        self.assertEqual(report["score"], 90)
        self.assertIn("Node.js / JavaScript / TypeScript", report["detected_stacks"])
        self.assertTrue(any("lifecycle scripts" in warning for warning in report["warnings"]))

    def test_malformed_package_json_is_reported(self):
        (self.root / "package.json").write_text("{broken", encoding="utf-8")
        report = evaluate_repository(self.root)
        self.assertTrue(any("could not be parsed" in warning for warning in report["warnings"]))
        self.assertEqual(report["adoption_status"], "REVIEW_REQUIRED")

    def test_missing_directory_is_rejected(self):
        with self.assertRaises(ValueError):
            evaluate_repository(self.root / "does-not-exist")

    def test_oversized_metadata_is_ignored(self):
        (self.root / "README.md").write_text("x" * 1_000_001, encoding="utf-8")
        report = evaluate_repository(self.root)
        self.assertFalse(report["files"]["readme_present"])


if __name__ == "__main__":
    unittest.main()
