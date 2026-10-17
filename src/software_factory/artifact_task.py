from __future__ import annotations

"""Strict allowlisted task adapter for bounded artifact integrity checks.

This is not a generic executor: it never interprets task text as a command,
executes source code, or releases jobs. All successful results remain review-gated.
"""
from pathlib import Path
from typing import Any, Mapping
from .artifact_workflow import create_and_verify_artifact


class ArtifactTaskError(ValueError):
    """Raised when an artifact task payload violates its contract."""


def handle_artifact_integrity_task(workspace: str | Path, task: Mapping[str, Any]) -> dict[str, Any]:
    """Run the built-in artifact_integrity task after validating every field.

    Required fields: kind, path, content. Optional fields: require_json,
    evidence_path. No arbitrary task kind or command is accepted.
    """
    if not isinstance(task, Mapping):
        raise ArtifactTaskError("Task must be a mapping")
    if task.get("kind") != "artifact_integrity":
        raise ArtifactTaskError("Only artifact_integrity tasks are allowed")
    path = task.get("path")
    if not isinstance(path, str) or not path.strip():
        raise ArtifactTaskError("path must be a non-empty relative path")
    content = task.get("content")
    if not isinstance(content, (str, bytes)):
        raise ArtifactTaskError("content must be text or bytes")
    require_json = task.get("require_json", False)
    if not isinstance(require_json, bool):
        raise ArtifactTaskError("require_json must be a boolean")
    evidence_path = task.get("evidence_path", "evidence/verification-report.json")
    if not isinstance(evidence_path, str) or not evidence_path.strip():
        raise ArtifactTaskError("evidence_path must be a non-empty relative path")
    return create_and_verify_artifact(workspace, path, content, require_json=require_json, evidence_path=evidence_path)
