"""Isolated workspace execution and command allowlist enforcement.

Provides:
- Disposable least-privilege workspaces for generated code and tests.
- Strict executable allowlist (rejects raw shell strings, pipes, and unvetted binaries).
- Output truncation limits and secret-safe error sanitization.
- Environment sanitization preventing host credential leakage.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Mapping

from .core import ValidationError
from .heartbeat import sanitize_error

# Explicitly allowlisted base binaries (without path or extension)
DEFAULT_ALLOWED_EXECUTABLES = frozenset({
    "python",
    "python3",
    "py",
    "pytest",
    "git",
    "node",
    "npm",
    "tsc",
})

# Prohibited shell command wrappers and redirection operators
PROHIBITED_TOKENS = frozenset({
    "|", ";", "&", "&&", "||", ">", ">>", "<",
    "bash", "sh", "zsh", "cmd", "cmd.exe", "powershell", "powershell.exe", "pwsh",
    "curl", "wget", "nc", "netcat", "socat",
})

# Safe host environment keys to preserve
SAFE_ENV_KEYS = frozenset({
    "PATH",
    "SYSTEMROOT",
    "WINDIR",
    "TEMP",
    "TMP",
    "PYTHONPATH",
    "HOME",
    "USERPROFILE",
    "LANG",
    "LC_ALL",
})


class SandboxViolationError(ValidationError):
    """Raised when a command violates the sandbox allowlist or containment policy."""


class SandboxPolicy:
    """Configurable containment policy for isolated command execution."""

    def __init__(
        self,
        allowed_executables: set[str] | frozenset[str] | None = None,
        default_timeout_seconds: float = 30.0,
        max_output_bytes: int = 500_000,
    ):
        self.allowed_executables = frozenset(allowed_executables or DEFAULT_ALLOWED_EXECUTABLES)
        self.default_timeout_seconds = max(1.0, float(default_timeout_seconds))
        self.max_output_bytes = max(1024, int(max_output_bytes))

    def validate_command(self, cmd: list[str]) -> str:
        """Validate that a command uses an allowlisted binary and no unsafe tokens."""
        if not isinstance(cmd, (list, tuple)) or not cmd:
            raise SandboxViolationError("Command must be a non-empty list of arguments.")

        for item in cmd:
            if not isinstance(item, str) or not item.strip():
                raise SandboxViolationError("Command arguments must be non-empty strings.")
            if item.strip() in PROHIBITED_TOKENS:
                raise SandboxViolationError(f"Argument '{item}' contains a prohibited shell or network token.")

        binary_path = cmd[0].strip()
        binary_name = Path(binary_path).name.lower()
        if binary_name.endswith(".exe"):
            binary_name = binary_name[:-4]

        if binary_name not in self.allowed_executables:
            raise SandboxViolationError(
                f"Binary '{binary_name}' is not in the sandbox allowlist: {sorted(self.allowed_executables)}"
            )

        return binary_name


class IsolatedWorkspace:
    """Disposable directory workspace providing contained subprocess execution."""

    def __init__(
        self,
        base_dir: str | Path | None = None,
        policy: SandboxPolicy | None = None,
        prefix: str = "sf-sandbox-",
    ):
        self.base_dir = Path(base_dir) if base_dir else None
        self.policy = policy or SandboxPolicy()
        self.prefix = prefix
        self._temp_dir: tempfile.TemporaryDirectory | None = None
        self._path: Path | None = Path(base_dir).resolve() if (base_dir and Path(base_dir).is_dir()) else None

    def __enter__(self) -> IsolatedWorkspace:
        if self._path is None:
            self._temp_dir = tempfile.TemporaryDirectory(prefix=self.prefix, dir=self.base_dir)
            self._path = Path(self._temp_dir.name).resolve()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self._temp_dir is not None:
            try:
                self._temp_dir.cleanup()
            except Exception:
                # On Windows NTFS, briefly open handles might delay immediate deletion
                time.sleep(0.05)
                try:
                    self._temp_dir.cleanup()
                except Exception:
                    pass
            self._temp_dir = None
            self._path = None

    @property
    def path(self) -> Path:
        if self._path is None:
            raise RuntimeError("IsolatedWorkspace has not been entered.")
        return self._path

    def write_file(self, rel_path: str, content: str) -> Path:
        """Write text file safely within the workspace boundary."""
        target = (self.path / rel_path).resolve()
        if not str(target).startswith(str(self.path)):
            raise SandboxViolationError(f"Path traversal detected: {rel_path}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return target

    def read_file(self, rel_path: str) -> str:
        """Read text file safely from within the workspace boundary."""
        target = (self.path / rel_path).resolve()
        if not str(target).startswith(str(self.path)):
            raise SandboxViolationError(f"Path traversal detected: {rel_path}")
        return target.read_text(encoding="utf-8")

    def file_exists(self, rel_path: str) -> bool:
        """Check if file exists safely within the workspace boundary."""
        target = (self.path / rel_path).resolve()
        if not str(target).startswith(str(self.path)):
            return False
        return target.is_file()


    def run_command(
        self,
        cmd: list[str],
        *,
        timeout_seconds: float | None = None,
        extra_env: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        """Execute an allowlisted command inside the workspace under containment."""
        self.policy.validate_command(cmd)

        timeout = float(timeout_seconds) if timeout_seconds is not None else self.policy.default_timeout_seconds

        # Sanitize environment: filter out host secrets, API keys, credentials
        sanitized_env = {
            k: v for k, v in os.environ.items()
            if k.upper() in SAFE_ENV_KEYS
        }
        if extra_env:
            for k, v in extra_env.items():
                if isinstance(k, str) and isinstance(v, str):
                    sanitized_env[k] = v

        t0 = time.perf_counter()
        timed_out = False
        return_code = -1
        stdout_text = ""
        stderr_text = ""

        try:
            proc = subprocess.Popen(
                cmd,
                cwd=str(self.path),
                env=sanitized_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=False,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            try:
                stdout_raw, stderr_raw = proc.communicate(timeout=timeout)
                return_code = proc.returncode
            except subprocess.TimeoutExpired:
                timed_out = True
                proc.kill()
                stdout_raw, stderr_raw = proc.communicate()
                return_code = -1

            stdout_text = sanitize_error(stdout_raw[: self.policy.max_output_bytes])
            stderr_text = sanitize_error(stderr_raw[: self.policy.max_output_bytes])

        except Exception as exc:
            stderr_text = sanitize_error(f"Execution error: {exc}")
            return_code = 1

        duration_ms = int((time.perf_counter() - t0) * 1000)

        return {
            "command": cmd,
            "return_code": return_code,
            "stdout": stdout_text,
            "stderr": stderr_text,
            "duration_ms": duration_ms,
            "timed_out": timed_out,
            "success": (return_code == 0 and not timed_out),
            "workspace": str(self.path),
        }

