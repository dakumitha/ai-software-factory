"""Tests for isolated workspace execution and command allowlist containment."""
import os
import sys
import unittest
from pathlib import Path

from software_factory.sandbox import (
    IsolatedWorkspace,
    SandboxPolicy,
    SandboxViolationError,
)


class SandboxTests(unittest.TestCase):
    def setUp(self):
        self.policy = SandboxPolicy(default_timeout_seconds=5.0)

    def test_allowlist_validation_permits_allowed_binaries(self):
        self.assertEqual(self.policy.validate_command(["python", "--version"]), "python")
        self.assertEqual(self.policy.validate_command(["git", "status"]), "git")

    def test_allowlist_validation_rejects_unallowlisted_binaries(self):
        with self.assertRaises(SandboxViolationError) as ctx:
            self.policy.validate_command(["cargo", "build"])
        self.assertIn("not in the sandbox allowlist", str(ctx.exception))

        with self.assertRaises(SandboxViolationError) as ctx:
            self.policy.validate_command(["curl", "https://example.com"])
        self.assertIn("contains a prohibited shell or network token", str(ctx.exception))

        with self.assertRaises(SandboxViolationError) as ctx:
            self.policy.validate_command(["bash", "-c", "echo hello"])
        self.assertIn("contains a prohibited shell or network token", str(ctx.exception))

    def test_allowlist_validation_rejects_shell_redirection_tokens(self):
        with self.assertRaises(SandboxViolationError) as ctx:
            self.policy.validate_command(["python", "script.py", "|", "grep"])
        self.assertIn("prohibited shell or network token", str(ctx.exception))

        with self.assertRaises(SandboxViolationError) as ctx:
            self.policy.validate_command(["python", "script.py", ">", "out.txt"])
        self.assertIn("prohibited shell or network token", str(ctx.exception))

    def test_isolated_workspace_executes_benign_python_command(self):
        py_exe = sys.executable
        with IsolatedWorkspace(policy=self.policy) as ws:
            ws_path = ws.path
            self.assertTrue(ws_path.exists())

            receipt = ws.run_command([py_exe, "-c", "print('sandbox_test_success')"])
            self.assertEqual(receipt["return_code"], 0)
            self.assertTrue(receipt["success"])
            self.assertFalse(receipt["timed_out"])
            self.assertIn("sandbox_test_success", receipt["stdout"])
            self.assertEqual(receipt["workspace"], str(ws_path))

        # After context exit, directory is cleaned up
        self.assertFalse(ws_path.exists())

    def test_isolated_workspace_sanitizes_environment(self):
        # Set a dummy secret in parent environment
        os.environ["SECRET_API_TOKEN_FOR_TEST"] = "super_secret_12345"
        try:
            py_exe = sys.executable
            code = (
                "import os; "
                "print('ENV_VAR_FOUND=' + str('SECRET_API_TOKEN_FOR_TEST' in os.environ))"
            )
            with IsolatedWorkspace(policy=self.policy) as ws:
                receipt = ws.run_command([py_exe, "-c", code])
                self.assertEqual(receipt["return_code"], 0)
                self.assertIn("ENV_VAR_FOUND=False", receipt["stdout"])
        finally:
            os.environ.pop("SECRET_API_TOKEN_FOR_TEST", None)

    def test_isolated_workspace_enforces_timeout(self):
        py_exe = sys.executable
        with IsolatedWorkspace(policy=self.policy) as ws:
            receipt = ws.run_command([py_exe, "-c", "import time; time.sleep(2.0)"], timeout_seconds=0.1)
            self.assertTrue(receipt["timed_out"])
            self.assertFalse(receipt["success"])
            self.assertNotEqual(receipt["return_code"], 0)


if __name__ == "__main__":
    unittest.main()

