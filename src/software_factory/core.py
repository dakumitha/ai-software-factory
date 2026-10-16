"""Small, dependency-free control plane for durable software-factory jobs.

This module deliberately does not execute generated code. It records work,
validates transitions, plans dependency-ordered tasks, and exposes an API.
Agent execution is added only behind an explicit, isolated adapter.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


STATES = {
    "DRAFT", "NEEDS_CLARIFICATION", "SPEC_READY", "PLAN_READY",
    "AWAITING_APPROVAL", "QUEUED", "RUNNING", "VERIFYING",
    "REVIEW_REQUIRED", "RELEASE_READY", "RELEASED", "BLOCKED",
    "FAILED", "CANCELLED", "PAUSED_QUOTA",
}
TRANSITIONS = {
    "DRAFT": {"NEEDS_CLARIFICATION", "SPEC_READY", "CANCELLED"},
    "NEEDS_CLARIFICATION": {"DRAFT", "SPEC_READY", "CANCELLED"},
    "SPEC_READY": {"PLAN_READY", "NEEDS_CLARIFICATION", "CANCELLED"},
    "PLAN_READY": {"AWAITING_APPROVAL", "SPEC_READY", "CANCELLED"},
    "AWAITING_APPROVAL": {"QUEUED", "PLAN_READY", "CANCELLED"},
    "QUEUED": {"RUNNING", "PAUSED_QUOTA", "BLOCKED", "CANCELLED"},
    "RUNNING": {"VERIFYING", "PAUSED_QUOTA", "BLOCKED", "FAILED", "CANCELLED"},
    "VERIFYING": {"REVIEW_REQUIRED", "RUNNING", "PAUSED_QUOTA", "BLOCKED", "FAILED"},
    "REVIEW_REQUIRED": {"RELEASE_READY", "RUNNING", "CANCELLED"},
    "RELEASE_READY": {"RELEASED", "REVIEW_REQUIRED", "CANCELLED"},
    "PAUSED_QUOTA": {"QUEUED", "CANCELLED"},
    "BLOCKED": {"QUEUED", "CANCELLED"},
    "FAILED": {"QUEUED", "CANCELLED"},
    "RELEASED": set(), "CANCELLED": set(),
}
TERMINAL = {"RELEASED", "CANCELLED"}
_LOCK = threading.RLock()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


class ValidationError(ValueError):
    """Input or state transition violates the domain contract."""


class Store:
    """SQLite persistence with append-only event history."""

    def __init__(self, path: str | Path = "data/factory.sqlite3"):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_db(self) -> None:
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL,
                    idea TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY, project_id TEXT NOT NULL,
                    state TEXT NOT NULL, spec_json TEXT NOT NULL,
                    tasks_json TEXT NOT NULL, budget_json TEXT NOT NULL,
                    checkpoint_json TEXT NOT NULL, created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(project_id) REFERENCES projects(id)
                );
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL, at TEXT NOT NULL,
                    actor TEXT NOT NULL, kind TEXT NOT NULL, payload_json TEXT NOT NULL,
                    FOREIGN KEY(job_id) REFERENCES jobs(id)
                );
            """)

    def create_project(self, name: str, idea: str) -> dict[str, Any]:
        name, idea = name.strip(), idea.strip()
        if not name or not idea:
            raise ValidationError("Project name and idea are required.")
        project = {"id": new_id("prj"), "name": name, "idea": idea, "created_at": utc_now()}
        with self.connect() as db:
            db.execute("INSERT INTO projects VALUES (?, ?, ?, ?)",
                       (project["id"], project["name"], project["idea"], project["created_at"]))
        return project

    def list_projects(self) -> list[dict[str, Any]]:
        with self.connect() as db:
            return [dict(row) for row in db.execute("SELECT * FROM projects ORDER BY created_at DESC")]

    def get_project(self, project_id: str) -> dict[str, Any] | None:
        with self.connect() as db:
            row = db.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
            return dict(row) if row else None

    def create_job(self, project_id: str, spec: dict[str, Any] | None = None,
                   tasks: list[dict[str, Any]] | None = None,
                   budget: dict[str, Any] | None = None) -> dict[str, Any]:
        if not self.get_project(project_id):
            raise ValidationError("Project does not exist.")
        task_list = validate_task_graph(tasks or [])
        now = utc_now()
        job = {
            "id": new_id("job"), "project_id": project_id, "state": "DRAFT",
            "spec": spec or {}, "tasks": task_list,
            "budget": budget or {"max_agent_calls": 0, "max_runtime_seconds": 0},
            "checkpoint": {"stage": "created", "resume_count": 0},
            "created_at": now, "updated_at": now,
        }
        with self.connect() as db:
            db.execute("""INSERT INTO jobs
                (id, project_id, state, spec_json, tasks_json, budget_json,
                 checkpoint_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (job["id"], project_id, job["state"], json.dumps(job["spec"]),
                 json.dumps(task_list), json.dumps(job["budget"]),
                 json.dumps(job["checkpoint"]), now, now))
            self._event(db, job["id"], "system", "job.created", {"state": "DRAFT"})
        return job

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with self.connect() as db:
            row = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            return self._decode_job(row) if row else None

    def list_jobs(self, project_id: str | None = None) -> list[dict[str, Any]]:
        with self.connect() as db:
            if project_id:
                rows = db.execute("SELECT * FROM jobs WHERE project_id=? ORDER BY created_at DESC", (project_id,))
            else:
                rows = db.execute("SELECT * FROM jobs ORDER BY created_at DESC")
            return [self._decode_job(row) for row in rows]

    @staticmethod
    def _decode_job(row: sqlite3.Row) -> dict[str, Any]:
        item = dict(row)
        for column, key in (("spec_json", "spec"), ("tasks_json", "tasks"),
                            ("budget_json", "budget"), ("checkpoint_json", "checkpoint")):
            item[key] = json.loads(item.pop(column))
        return item

    @staticmethod
    def _event(db: sqlite3.Connection, job_id: str, actor: str,
               kind: str, payload: dict[str, Any]) -> None:
        db.execute("INSERT INTO events(job_id, at, actor, kind, payload_json) VALUES (?, ?, ?, ?, ?)",
                   (job_id, utc_now(), actor, kind, json.dumps(payload, sort_keys=True)))

    def transition(self, job_id: str, target: str, actor: str = "owner",
                   reason: str = "") -> dict[str, Any]:
        if target not in STATES:
            raise ValidationError(f"Unknown state: {target}")
        with _LOCK, self.connect() as db:
            row = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            if not row:
                raise ValidationError("Job does not exist.")
            current = row["state"]
            if target not in TRANSITIONS[current]:
                raise ValidationError(f"Transition {current} -> {target} is not allowed.")
            if target == "RELEASED":
                raise ValidationError("Release requires verified evidence and a separate release controller.")
            now = utc_now()
            checkpoint = json.loads(row["checkpoint_json"])
            checkpoint.update({"stage": target.lower(), "last_reason": reason})
            if current == "PAUSED_QUOTA" and target == "QUEUED":
                checkpoint["resume_count"] = int(checkpoint.get("resume_count", 0)) + 1
            db.execute("UPDATE jobs SET state=?, checkpoint_json=?, updated_at=? WHERE id=?",
                       (target, json.dumps(checkpoint), now, job_id))
            self._event(db, job_id, actor, "job.transition", {
                "from": current, "to": target, "reason": reason,
            })
        return self.get_job(job_id)  # type: ignore[return-value]

    def events(self, job_id: str) -> list[dict[str, Any]]:
        with self.connect() as db:
            rows = db.execute("SELECT * FROM events WHERE job_id=? ORDER BY id", (job_id,)).fetchall()
        return [{"id": r["id"], "at": r["at"], "actor": r["actor"], "kind": r["kind"],
                 "payload": json.loads(r["payload_json"])} for r in rows]


def validate_task_graph(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Validate unique task IDs, requirement traceability, and acyclic dependencies."""
    if not isinstance(tasks, list):
        raise ValidationError("Tasks must be a list.")
    ids: set[str] = set()
    normalized = []
    for task in tasks:
        if not isinstance(task, dict):
            raise ValidationError("Each task must be an object.")
        task_id = str(task.get("id", "")).strip()
        title = str(task.get("title", "")).strip()
        requirements = task.get("requirement_ids", [])
        depends = task.get("depends_on", [])
        if not task_id or task_id in ids:
            raise ValidationError("Task IDs must be non-empty and unique.")
        if not title:
            raise ValidationError(f"Task {task_id} requires a title.")
        if not isinstance(requirements, list) or not all(isinstance(x, str) and x.strip() for x in requirements):
            raise ValidationError(f"Task {task_id} requirement_ids must be a list of non-empty strings.")
        if not isinstance(depends, list) or not all(isinstance(x, str) for x in depends):
            raise ValidationError(f"Task {task_id} depends_on must be a list of strings.")
        ids.add(task_id)
        normalized.append({"id": task_id, "title": title,
                           "requirement_ids": sorted(set(requirements)),
                           "depends_on": sorted(set(depends)),
                           "acceptance_checks": task.get("acceptance_checks", [])})
    for task in normalized:
        missing = set(task["depends_on"]) - ids
        if missing:
            raise ValidationError(f"Task {task['id']} has unknown dependencies: {sorted(missing)}")
        if task["id"] in task["depends_on"]:
            raise ValidationError(f"Task {task['id']} cannot depend on itself.")
    by_id = {task["id"]: task for task in normalized}
    visiting: set[str] = set()
    visited: set[str] = set()
    def visit(task_id: str) -> None:
        if task_id in visiting:
            raise ValidationError("Task dependencies contain a cycle.")
        if task_id in visited:
            return
        visiting.add(task_id)
        for dependency in by_id[task_id]["depends_on"]:
            visit(dependency)
        visiting.remove(task_id)
        visited.add(task_id)
    for task_id in by_id:
        visit(task_id)
    return normalized


def ready_tasks(tasks: list[dict[str, Any]], completed: set[str] | None = None) -> list[dict[str, Any]]:
    """Return tasks whose dependencies are completed, preserving declared order."""
    completed = completed or set()
    return [t for t in tasks if t["id"] not in completed and set(t["depends_on"]) <= completed]


class ApiHandler(BaseHTTPRequestHandler):
    store: Store

    def log_message(self, format: str, *args: Any) -> None:
        # Avoid writing user project ideas to default request logs.
        return

    def _send(self, status: int, data: Any) -> None:
        raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def _body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length < 1 or length > 1_000_000:
            raise ValidationError("Request body must be between 1 byte and 1 MB.")
        body = json.loads(self.rfile.read(length))
        if not isinstance(body, dict):
            raise ValidationError("JSON body must be an object.")
        return body

    def do_GET(self) -> None:
        path = urlparse(self.path).path.rstrip("/") or "/"
        if path == "/health":
            return self._send(200, {"ok": True, "service": "ai-software-factory-control-plane", "execution_enabled": False})
        if path == "/projects":
            return self._send(200, {"items": self.store.list_projects()})
        if path == "/jobs":
            return self._send(200, {"items": self.store.list_jobs()})
        parts = path.strip("/").split("/")
        if len(parts) == 2 and parts[0] == "projects":
            project = self.store.get_project(parts[1])
            return self._send(200, project) if project else self._send(404, {"error": "Project not found"})
        if len(parts) == 2 and parts[0] == "jobs":
            job = self.store.get_job(parts[1])
            return self._send(200, job) if job else self._send(404, {"error": "Job not found"})
        if len(parts) == 3 and parts[0] == "jobs" and parts[2] == "events":
            if not self.store.get_job(parts[1]):
                return self._send(404, {"error": "Job not found"})
            return self._send(200, {"items": self.store.events(parts[1])})
        return self._send(404, {"error": "Not found"})

    def do_POST(self) -> None:
        path = urlparse(self.path).path.rstrip("/")
        try:
            body = self._body()
            if path == "/projects":
                return self._send(201, self.store.create_project(body.get("name", ""), body.get("idea", "")))
            if path == "/jobs":
                return self._send(201, self.store.create_job(
                    str(body.get("project_id", "")), body.get("spec"), body.get("tasks"), body.get("budget")))
            parts = path.strip("/").split("/")
            if len(parts) == 3 and parts[0] == "jobs" and parts[2] == "transition":
                # API intentionally does not accept arbitrary actors or release-to-production.
                return self._send(200, self.store.transition(parts[1], str(body.get("target", "")),
                                                             actor="api-owner", reason=str(body.get("reason", ""))))
            return self._send(404, {"error": "Not found"})
        except (ValidationError, json.JSONDecodeError, TypeError) as exc:
            return self._send(400, {"error": str(exc)})
        except Exception:
            return self._send(500, {"error": "Internal error. Check server-side diagnostics."})


def serve(host: str = "127.0.0.1", port: int = 8080,
          database: str = "data/factory.sqlite3") -> None:
    if host not in {"127.0.0.1", "localhost", "::1"} and os.environ.get("FACTORY_ALLOW_REMOTE") != "1":
        raise RuntimeError("Remote binding is disabled by default. Set FACTORY_ALLOW_REMOTE=1 only behind authenticated TLS.")
    ApiHandler.store = Store(database)
    server = ThreadingHTTPServer((host, port), ApiHandler)
    print(f"AI Software Factory control plane listening on http://{host}:{port}")
    print(f"Database: {database}; agent execution: disabled")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
