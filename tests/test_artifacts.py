import hashlib
import tempfile
import unittest
from pathlib import Path

from software_factory.artifacts import ArtifactError, write_artifact, write_json_artifact


class ArtifactWriterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "workspace"

    def tearDown(self):
        self.tmp.cleanup()

    def test_writes_content_and_returns_integrity_metadata(self):
        result = write_artifact(self.root, "src/example.txt", "hello")
        self.assertEqual((self.root / "src/example.txt").read_text(), "hello")
        self.assertEqual(result["sha256"], hashlib.sha256(b"hello").hexdigest())
        self.assertEqual(result["size_bytes"], 5)

    def test_rejects_parent_traversal_and_absolute_paths(self):
        for path in ("../outside.txt", "src/../../outside.txt", "/tmp/outside.txt", ""):
            with self.subTest(path=path), self.assertRaises(ArtifactError):
                write_artifact(self.root, path, "no")

    def test_does_not_overwrite_without_explicit_permission(self):
        write_artifact(self.root, "out.txt", "first")
        with self.assertRaises(ArtifactError):
            write_artifact(self.root, "out.txt", "second")
        self.assertEqual((self.root / "out.txt").read_text(), "first")
        write_artifact(self.root, "out.txt", "second", overwrite=True)
        self.assertEqual((self.root / "out.txt").read_text(), "second")

    def test_rejects_oversized_artifact(self):
        with self.assertRaises(ArtifactError):
            write_artifact(self.root, "large.bin", b"x" * 1_000_001)
        self.assertFalse((self.root / "large.bin").exists())

    def test_rejects_symlink_escape(self):
        outside = Path(self.tmp.name) / "outside"
        outside.mkdir()
        self.root.mkdir()
        try:
            (self.root / "link").symlink_to(outside, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("Symlinks unavailable on this platform")
        with self.assertRaises(ArtifactError):
            write_artifact(self.root, "link/pwned.txt", "no")
        self.assertFalse((outside / "pwned.txt").exists())

    def test_writes_json_artifact(self):
        result = write_json_artifact(self.root, "reports/report.json", {"ok": True})
        self.assertTrue(result["sha256"])
        self.assertIn('"ok": true', (self.root / "reports/report.json").read_text())


if __name__ == "__main__":
    unittest.main()
