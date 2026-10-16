"""Create a bounded artifact and independently verify its recorded bytes.

This is a local helper workflow, not a sandbox or source-code test runner. It
writes only beneath a caller-selected workspace, compares the file's digest
using a separate read-back verification step, and persists the evidence report.
A successful result means file-integrity checks passed, not that the artifact is
correct, safe, buildable, or ready to release.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .artifacts import write_artifact
from .verification import save_verification_report, verify_artifact


def create_and_verify_artifact(
    workspace: str | Path,
    relative_path: str,
    content: str | bytes,
    *,
    require_json: bool = False,
    evidence_path: str = "evidence/verification-report.json",
) -> dict[str, Any]:
    """Write an artifact, read it back independently, and save a JSON evidence report.

    The output file is never overwritten implicitly. The evidence report is also
    create-only by default, so repeated runs should use a fresh workspace or an
    explicitly chosen evidence path. Any failed check remains visible in the
    returned report; this function never promotes a job to release.
    """
    # First receipt is created by the bounded writer. Its digest becomes the
    # expected value for the independent read-back verifier.
    receipt = write_artifact(workspace, relative_path, content)
    report = verify_artifact(
        workspace,
        relative_path,
        expected_sha256=receipt["sha256"],
        require_json=require_json,
    )
    evidence_receipt = save_verification_report(
        workspace,
        evidence_path,
        report,
    )

    # REVIEW_REQUIRED is intentional even when byte-level checks pass: this
    # workflow does not run application tests or judge functional correctness.
    return {
        "workflow": "bounded_artifact_integrity",
        "status": report["status"],
        "next_state": "REVIEW_REQUIRED",
        "artifact": receipt,
        "verification": report,
        "evidence": evidence_receipt,
        "release_performed": False,
        "limitations": [
            "Only file containment, size, digest, and optional JSON syntax were checked.",
            "No source code, tests, scripts, or binaries were executed.",
            "Human review and appropriate project-specific tests remain required.",
        ],
    }
