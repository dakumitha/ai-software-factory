import hashlib
import tempfile
import unittest
from pathlib import Path

from software_factory.verification import (
    VerificationError, save_verification_report, verify_artifact,
)


class ArtifactVerificationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "workspace"
        self.root.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_verifies_digest_and_json_syntax(self):
        data = b'{"ok": true}\n'
        (self.root / "result.json").write_bytes(data)
        report = verify_artifact(
            self.root, "result.json",
            expected_sha256=hashlib.sha256(data).hexdigest(), require_json=True,
        )
        self.assertEqual(report["status"], "PASSED")
        self.assertTrue(all(item["passed"] for item in report["checks"]))

    def test_hash_mismatch_is_a_failed_report_not_an_exception(self):
        (self.root / "result.txt").write_text("hello")
        report = verify_artifact(self.root, "result.txt", expected_sha256="0" * 64)
        self.assertEqual(report["status"], "FAILED")
        self.assertFalse(next(c for c in report["checks"] if c["check"] == "sha256_match")["passed"])

    def test_invalid_json_is_failed(self):
        (self.root / "bad.json").write_text("{broken")
        report = verify_artifact(self.root, "bad.json", require_json=True)
        self.assertEqual(report["status"], "FAILED")

    def test_missing_and_traversal_paths_are_rejected(self):
        with self.assertRaises(VerificationError):
            verify_artifact(self.root, "missing.txt")
        with self.assertRaises(VerificationError):
            verify_artifact(self.root, "../outside.txt")

    def test_symlink_path_is_rejected(self):
        outside = Path(self.tmp.name) / "outside.txt"
        outside.write_text("secret")
        try:
            (self.root / "link.txt").symlink_to(outside)
        except (OSError, NotImplementedError):
            self.skipTest("Symlinks unavailable on this platform")
        with self.assertRaises(VerificationError):
            verify_artifact(self.root, "link.txt")

    def test_saves_report_as_bounded_json_artifact(self):
        (self.root / "result.txt").write_text("hello")
        report = verify_artifact(self.root, "result.txt")
        receipt = save_verification_report(self.root, "evidence/result.json", report)
        self.assertTrue(receipt["sha256"])
        self.assertIn('"status": "PASSED"', (self.root / "evidence/result.json").read_text())

    def test_rejects_invalid_expected_digest(self):
        (self.root / "result.txt").write_text("hello")
        with self.assertRaises(VerificationError):
            verify_artifact(self.root, "result.txt", expected_sha256="not-a-hash")


if __name__ == "__main__":
    unittest.main()
