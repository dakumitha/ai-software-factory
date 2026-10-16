"""Versioned, traceable specification workflow for the AI Software Factory."""
from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, timezone
from typing import Any

from .core import Store, ValidationError, new_id, utc_now


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:48] or "project"


def _validate_spec(spec: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(spec, dict):
        raise ValidationError("Specification must be an object.")
    title = str(spec.get("title", "")).strip()
    goal = str(spec.get("goal", "")).strip()
    requirements = spec.get("requirements", [])
    questions = spec.get("open_questions", [])
    if not title or not goal:
        raise ValidationError("Specification requires a title and a goal.")
    if not isinstance(requirements, list):
        raise ValidationError("requirements must be a list.")
    seen: set[str] = set()
    normalized = []
    for req in requirements:
        if not isinstance(req, dict):
            raise ValidationError("Each requirement must be an object.")
        rid = str(req.get("id", "")).strip()
        description = str(req.get("description", "")).strip()
        acceptance = req.get("acceptance_criteria", [])
        if not rid or rid in seen:
            raise ValidationError("Requirement IDs must be non-empty and unique.")
        if not description:
            raise ValidationError(f"{rid} needs a description.")
        if not isinstance(acceptance, list) or not acceptance or not all(
            isinstance(x, str) and x.strip() for x in acceptance
        ):
            raise ValidationError(f"{rid} needs at least one measurable acceptance criterion.")
        seen.add(rid)
        normalized.append({
            "id": rid,
            "description": description,
            "priority": str(req.get("priority", "must")).lower(),
            "acceptance_criteria": [x.strip() for x in acceptance],
        })
    if not isinstance(questions, list) or not all(isinstance(x, str) and x.strip() for x in questions):
        raise ValidationError("open_questions must be a list of non-empty strings.")
    return {
        "title": title,
        "goal": goal,
        "requirements": normalized,
        "open_questions": [q.strip() for q in questions],
        "assumptions": spec.get("assumptions", []),
        "constraints": spec.get("constraints", []),
        "updated_at": utc_now(),
    }


class SpecStore:
    """Immutable specification revisions with explicit approval metadata."""

    def __init__(self, store: Store):
        self.store = store
        with store.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS specifications (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    spec_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    approved_at TEXT,
                    UNIQUE(project_id, version),
                    FOREIGN KEY(project_id) REFERENCES projects(id)
                );
            """)

    def save(self, project_id: str, spec: dict[str, Any]) -> dict[str, Any]:
        if not self.store.get_project(project_id):
            raise ValidationError("Project does not exist.")
        normalized = _validate_spec(spec)
        with self.store.connect() as db:
            version = db.execute(
                "SELECT COALESCE(MAX(version), 0) + 1 FROM specifications WHERE project_id=?",
                (project_id,),
            ).fetchone()[0]
            item = {
                "id": new_id("spec"), "project_id": project_id, "version": version,
                "spec": normalized, "status": "DRAFT", "created_at": utc_now(),
                "approved_at": None,
            }
            db.execute(
                "INSERT INTO specifications(id, project_id, version, spec_json, status, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (item["id"], project_id, version, json.dumps(normalized), "DRAFT", item["created_at"]),
            )
            return item

    def list(self, project_id: str) -> list[dict[str, Any]]:
        with self.store.connect() as db:
            rows = db.execute(
                "SELECT * FROM specifications WHERE project_id=? ORDER BY version DESC", (project_id,)
            ).fetchall()
        return [self._decode(row) for row in rows]

    def get(self, spec_id: str) -> dict[str, Any] | None:
        with self.store.connect() as db:
            row = db.execute("SELECT * FROM specifications WHERE id=?", (spec_id,)).fetchone()
        return self._decode(row) if row else None

    @staticmethod
    def _decode(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"], "project_id": row["project_id"], "version": row["version"],
            "spec": json.loads(row["spec_json"]), "status": row["status"],
            "created_at": row["created_at"], "approved_at": row["approved_at"],
        }

    def approve(self, spec_id: str, actor: str = "owner") -> dict[str, Any]:
        with self.store.connect() as db:
            row = db.execute("SELECT * FROM specifications WHERE id=?", (spec_id,)).fetchone()
            if not row:
                raise ValidationError("Specification does not exist.")
            if row["status"] == "APPROVED":
                return self._decode(row)
            spec = json.loads(row["spec_json"])
            if spec["open_questions"]:
                raise ValidationError("Resolve open questions before approving the specification.")
            approved_at = utc_now()
            db.execute(
                "UPDATE specifications SET status='APPROVED', approved_at=? WHERE id=?",
                (approved_at, spec_id),
            )
            # Record the decision in the job-independent audit stream associated with the project
            # by storing an event in the dedicated specification audit table.
            db.execute(
                """CREATE TABLE IF NOT EXISTS specification_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    spec_id TEXT NOT NULL, at TEXT NOT NULL, actor TEXT NOT NULL,
                    kind TEXT NOT NULL, payload_json TEXT NOT NULL,
                    FOREIGN KEY(spec_id) REFERENCES specifications(id)
                )"""
            )
            db.execute(
                "INSERT INTO specification_events(spec_id, at, actor, kind, payload_json) VALUES (?, ?, ?, ?, ?)",
                (spec_id, approved_at, actor, "spec.approved",
                 json.dumps({"version": row["version"], "project_id": row["project_id"]})),
            )
        return self.get(spec_id)  # type: ignore[return-value]

    def events(self, spec_id: str) -> list[dict[str, Any]]:
        with self.store.connect() as db:
            rows = db.execute(
                "SELECT * FROM specification_events WHERE spec_id=? ORDER BY id", (spec_id,)
            ).fetchall()
        return [{"id": row["id"], "at": row["at"], "actor": row["actor"],
                 "kind": row["kind"], "payload": json.loads(row["payload_json"])} for row in rows]


def build_plan(spec: dict[str, Any]) -> list[dict[str, Any]]:
    """Create deterministic starter tasks from accepted requirement records."""
    normalized = _validate_spec(spec)
    tasks = [{
        "id": "foundation",
        "title": "Create project skeleton and baseline engineering checks",
        "requirement_ids": [],
        "depends_on": [],
        "acceptance_checks": ["Repository structure exists", "Baseline checks are configured"],
    }]
    for req in normalized["requirements"]:
        task_id = "req-" + _slug(req["id"])
        tasks.append({
            "id": task_id,
            "title": f"Implement: {req['description']}",
            "requirement_ids": [req["id"]],
            "depends_on": ["foundation"],
            "acceptance_checks": req["acceptance_criteria"],
        })
    tasks.append({
        "id": "integration-verification",
        "title": "Run integration checks and produce a verification report",
        "requirement_ids": [req["id"] for req in normalized["requirements"]],
        "depends_on": [task["id"] for task in tasks],
        "acceptance_checks": ["All required checks have recorded outcomes", "Failures block release"],
    })
    return tasks
