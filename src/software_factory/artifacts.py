"""Bounded local artifact storage for generated outputs.

This is a path-safe convenience layer, not an OS sandbox. The workspace must
remain private to the factory process and must not contain secrets.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
from typing import Any

MAX_ARTIFACT_BYTES = 1_000_000


class ArtifactError(ValueError):
    """Artifact path, size, or write policy rejected the request."""


def _safe_target(root: Path, relative_path: str) -> Path:
    if not isinstance(relative_path, str) or not relative_path.strip():
        raise ArtifactError("Artifact path must be a non-empty relative path")
    if "\\" in relative_path or "\x00" in relative_path:
        raise ArtifactError("Artifact path contains unsupported characters")
    rel = PurePosixPath(relative_path)
    if rel.is_absolute() or any(part in {"", ".", ".."} for part in rel.parts):
        raise ArtifactError("Artifact path must not be absolute or traverse parent directories")
    base = root.expanduser().resolve()
    target = base.joinpath(*rel.parts)
    # Refuse existing symlinks in every component, even if they resolve inside root.
    current = base
    for part in rel.parts:
        current = current / part
        if current.is_symlink():
            raise ArtifactError("Symlinks are not allowed in artifact paths")
    resolved_parent = target.parent.resolve()
    if not resolved_parent.is_relative_to(base):
        raise ArtifactError("Artifact path escapes the workspace")
    if target.exists() and not target.resolve().is_relative_to(base):
        raise ArtifactError("Artifact path escapes the workspace")
    return target


def write_artifact(root: str | Path, relative_path: str, content: str | bytes,
                   *, overwrite: bool = False) -> dict[str, Any]:
    """Write one bounded UTF-8/binary artifact and return integrity metadata.

    Existing files are never overwritten unless overwrite=True. Parent folders
    are created only beneath the selected workspace.
    """
    base = Path(root).expanduser().resolve()
    base.mkdir(parents=True, exist_ok=True)
    target = _safe_target(base, relative_path)
    if isinstance(content, str):
        data = content.encode("utf-8")
    elif isinstance(content, bytes):
        data = content
    else:
        raise ArtifactError("Artifact content must be text or bytes")
    if len(data) > MAX_ARTIFACT_BYTES:
        raise ArtifactError("Artifact exceeds the 1 MB limit")
    target.parent.mkdir(parents=True, exist_ok=True)
    # Revalidate after directory creation to catch pre-existing symlink paths.
    target = _safe_target(base, relative_path)
    flags = os.O_WRONLY | os.O_CREAT
    flags |= os.O_TRUNC if overwrite else os.O_EXCL
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(target, flags, 0o600)
    except FileExistsError as exc:
        raise ArtifactError("Artifact already exists; pass overwrite=True to replace it") from exc
    except OSError as exc:
        raise ArtifactError(f"Artifact could not be created safely: {exc}") from exc
    with os.fdopen(fd, "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    return {
        "path": relative_path,
        "size_bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "overwritten": bool(overwrite),
    }


def write_json_artifact(root: str | Path, relative_path: str, value: Any,
                        *, overwrite: bool = False) -> dict[str, Any]:
    try:
        rendered = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    except (TypeError, ValueError) as exc:
        raise ArtifactError(f"Value is not JSON serializable: {exc}") from exc
    return write_artifact(root, relative_path, rendered, overwrite=overwrite)
