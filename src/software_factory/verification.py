"""Non-executing artifact verification and evidence reports."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path, PurePosixPath
from typing import Any

from .artifacts import ArtifactError, write_json_artifact

MAX_VERIFY_BYTES = 1_000_000


class VerificationError(ValueError):
    """Verification input or artifact path is invalid."""


def verify_artifact(root: str | Path, relative_path: str, *,
                    expected_sha256: str | None = None,
                    require_json: bool = False) -> dict[str, Any]:
    """Verify file containment, size, digest, and optionally JSON syntax.

    This never imports, executes, or interprets the artifact as code.
    """
    if not isinstance(relative_path, str) or not relative_path.strip():
        raise VerificationError("Artifact path must be a non-empty relative path")
    if "\\" in relative_path or "\x00" in relative_path:
        raise VerificationError("Artifact path contains unsupported characters")
    rel = PurePosixPath(relative_path)
    if rel.is_absolute() or any(part in {"", ".", ".."} for part in rel.parts):
        raise VerificationError("Artifact path must not be absolute or traverse parent directories")
    if expected_sha256 is not None and not re.fullmatch(r"[0-9a-fA-F]{64}", expected_sha256):
        raise VerificationError("expected_sha256 must be a 64-character hexadecimal digest")

    base = Path(root).expanduser().resolve()
    target = base.joinpath(*rel.parts)
    current = base
    for part in rel.parts:
        current = current / part
        if current.is_symlink():
            raise VerificationError("Symlinks are not allowed in artifact paths")
    try:
        resolved = target.resolve(strict=True)
        if not resolved.is_relative_to(base):
            raise VerificationError("Artifact path escapes the workspace")
        if not resolved.is_file():
            raise VerificationError("Artifact is not a regular file")
        size = resolved.stat().st_size
        if size > MAX_VERIFY_BYTES:
            raise VerificationError("Artifact exceeds the 1 MB verification limit")
        data = resolved.read_bytes()
    except FileNotFoundError as exc:
        raise VerificationError("Artifact does not exist") from exc
    except OSError as exc:
        raise VerificationError(f"Artifact could not be read: {exc}") from exc

    digest = hashlib.sha256(data).hexdigest()
    checks = [
        {"check": "workspace_containment", "passed": True},
        {"check": "size_limit", "passed": True, "size_bytes": size, "maximum_bytes": MAX_VERIFY_BYTES},
    ]
    if expected_sha256 is not None:
        matched = digest.lower() == expected_sha256.lower()
        checks.append({"check": "sha256_match", "passed": matched,
                       "expected": expected_sha256.lower(), "actual": digest})
    if require_json:
        try:
            json.loads(data.decode("utf-8"))
            json_valid = True
            detail = "Valid UTF-8 JSON"
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            json_valid = False
            detail = f"{type(exc).__name__}: {str(exc)[:300]}"
        checks.append({"check": "json_syntax", "passed": json_valid, "detail": detail})

    passed = all(check["passed"] for check in checks)
    return {
        "schema_version": 1,
        "verification_type": "non_executing_artifact_check",
        "artifact_path": relative_path,
        "size_bytes": size,
        "sha256": digest,
        "checks": checks,
        "status": "PASSED" if passed else "FAILED",
        "limitations": [
            "This verifies file properties only; it does not establish correctness, safety, licence compliance, or buildability.",
            "No source code, tests, scripts, or binaries were executed.",
        ],
    }


def save_verification_report(root: str | Path, report_path: str, report: dict[str, Any],
                             *, overwrite: bool = False) -> dict[str, Any]:
    """Persist a verification report as JSON within the same bounded workspace."""
    try:
        return write_json_artifact(root, report_path, report, overwrite=overwrite)
    except ArtifactError as exc:
        raise VerificationError(str(exc)) from exc
