"""Durable, dependency-free control plane for software-factory jobs."""
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
    "DRAFT", "NEEDS_CLARIFICATION", "SPEC_READY", "PLAN_READY", "AWAITING_APPROVAL",
    "QUEUED", "RUNNING", "VERIFYING", "REVIEW_REQUIRED", "RELEASE_READY", "RELEASED",
    "BLOCKED", "FAILED", "CANCELLED", "PAUSED_QUOTA",
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
    "RELEASE_READY": {"REVIEW_REQUIRED", "CANCELLED"},
    "PAUSED_QUOTA": {"QUEUED", "CANCELLED"},
    "BLOCKED": {"QUEUED", "CANCELLED"},
    "FAILED": {"QUEUED", "CANCELLED"},
    "RELEASED": set(), "CANCELLED": set(),
}
_LOCK = threading.RLock()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


class ValidationError(ValueError):
    """Input or state transition violates the domain contract."""


class Store:
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
        """Apply ordered, additive schema migrations before the store is used.

        Databases created before migration tracking are treated as schema v1;
        their existing tables and records are preserved.
        """
        with self.connect() as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL
                )
            """)
            applied = {
                int(row["version"])
                for row in db.execute("SELECT version FROM schema_migrations")
            }
            latest_known = 2
            if applied and max(applied) > latest_known:
                raise RuntimeError(
                    f"Database schema version {max(applied)} is newer than this application "
                    f"supports (latest known: {latest_known})."
                )

            if 1 not in applied:
                db.execute("""
                    CREATE TABLE IF NOT EXISTS projects (
                        id TEXT PRIMARY KEY, name TEXT NOT NULL, idea TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    )
                """)
                db.execute("""
                    CREATE TABLE IF NOT EXISTS jobs (
                        id TEXT PRIMARY KEY, project_id TEXT NOT NULL, state TEXT NOT NULL,
                        spec_json TEXT NOT NULL, tasks_json TEXT NOT NULL, budget_json TEXT NOT NULL,
                        checkpoint_json TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                        FOREIGN KEY(project_id) REFERENCES projects(id)
                    )
                """)
                db.execute("""
                    CREATE TABLE IF NOT EXISTS events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT, job_id TEXT NOT NULL, at TEXT NOT NULL,
                        actor TEXT NOT NULL, kind TEXT NOT NULL, payload_json TEXT NOT NULL,
                        FOREIGN KEY(job_id) REFERENCES jobs(id)
                    )
                """)
                db.execute(
                    "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                    (1, utc_now()),
                )

            if 2 not in applied:
                db.execute("CREATE INDEX IF NOT EXISTS idx_jobs_state_updated_at ON jobs(state, updated_at)")
                db.execute("CREATE INDEX IF NOT EXISTS idx_events_job_id_id ON events(job_id, id)")
                db.execute(
                    "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                    (2, utc_now()),
                )

    def schema_version(self) -> int:
        """Return the highest successfully recorded schema migration."""
        with self.connect() as db:
            row = db.execute("SELECT MAX(version) AS version FROM schema_migrations").fetchone()
        return int(row["version"] or 0)

    def list_interrupted_jobs(self) -> list[dict[str, Any]]:
        """List jobs left in active execution states for explicit recovery review.

        This is intentionally observational: without worker leases/heartbeats,
        the store cannot safely decide whether another process still owns a job.
        """
        with self.connect() as db:
            rows = db.execute(
                "SELECT * FROM jobs WHERE state IN ('RUNNING', 'VERIFYING') "
                "ORDER BY updated_at ASC, id ASC"
            ).fetchall()
        candidates = []
        for row in rows:
            job = self._decode_job(row)
            checkpoint = job["checkpoint"]
            candidates.append({
                "job_id": job["id"],
                "project_id": job["project_id"],
                "state": job["state"],
                "updated_at": job["updated_at"],
                "current_task_id": checkpoint.get("current_task_id"),
                "completed_task_ids": checkpoint.get("completed_task_ids", []),
                "recovery_status": "operator_review_required",
            })
        return candidates


    def backup_to(self, destination: str | Path) -> Path:
        """Create a consistent SQLite backup at destination.

        The caller is responsible for protecting the backup file and its
        containing directory because they may contain project and job data.
        """
        target = Path(destination)
        if self.path != ":memory:" and Path(self.path).resolve() == target.resolve():
            raise ValidationError("Backup destination must differ from the live database.")
        target.parent.mkdir(parents=True, exist_ok=True)
        source = self.connect()
        backup = sqlite3.connect(str(target), timeout=10)
        try:
            source.backup(backup)
        finally:
            backup.close()
            source.close()
        return target

    def create_project(self, name: str, idea: str) -> dict[str, Any]:
        name, idea = name.strip(), idea.strip()
        if not name or not idea:
            raise ValidationError("Project name and idea are required.")
        item = {"id": new_id("prj"), "name": name, "idea": idea, "created_at": utc_now()}
        with self.connect() as db:
            db.execute("INSERT INTO projects VALUES (?, ?, ?, ?)",
                       (item["id"], item["name"], item["idea"], item["created_at"]))
        return item

    def list_projects(self) -> list[dict[str, Any]]:
        with self.connect() as db:
            return [dict(r) for r in db.execute("SELECT * FROM projects ORDER BY created_at DESC")]

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
        item = {"id": new_id("job"), "project_id": project_id, "state": "DRAFT",
                "spec": spec or {}, "tasks": task_list,
                "budget": budget or {"max_agent_calls": 0, "max_runtime_seconds": 0},
                "checkpoint": {"stage": "created", "resume_count": 0},
                "created_at": now, "updated_at": now}
        with self.connect() as db:
            db.execute("""INSERT INTO jobs
                (id, project_id, state, spec_json, tasks_json, budget_json, checkpoint_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (item["id"], project_id, item["state"], json.dumps(item["spec"]), json.dumps(task_list),
                 json.dumps(item["budget"]), json.dumps(item["checkpoint"]), now, now))
            self._event(db, item["id"], "system", "job.created", {"state": "DRAFT"})
        return item

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with self.connect() as db:
            row = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            return self._decode_job(row) if row else None

    def list_jobs(self, project_id: str | None = None) -> list[dict[str, Any]]:
        with self.connect() as db:
            rows = db.execute("SELECT * FROM jobs WHERE project_id=? ORDER BY created_at DESC", (project_id,)) if project_id else db.execute("SELECT * FROM jobs ORDER BY created_at DESC")
            return [self._decode_job(r) for r in rows]

    @staticmethod
    def _decode_job(row: sqlite3.Row) -> dict[str, Any]:
        item = dict(row)
        for col, key in (("spec_json", "spec"), ("tasks_json", "tasks"),
                         ("budget_json", "budget"), ("checkpoint_json", "checkpoint")):
            item[key] = json.loads(item.pop(col))
        return item

    @staticmethod
    def _event(db: sqlite3.Connection, job_id: str, actor: str, kind: str, payload: dict[str, Any]) -> None:
        db.execute("INSERT INTO events(job_id, at, actor, kind, payload_json) VALUES (?, ?, ?, ?, ?)",
                   (job_id, utc_now(), actor, kind, json.dumps(payload, sort_keys=True)))

    def transition(self, job_id: str, target: str, actor: str = "owner", reason: str = "") -> dict[str, Any]:
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
            checkpoint = json.loads(row["checkpoint_json"])
            checkpoint.update({"stage": target.lower(), "last_reason": reason})
            if current == "PAUSED_QUOTA" and target == "QUEUED":
                checkpoint["resume_count"] = int(checkpoint.get("resume_count", 0)) + 1
            now = utc_now()
            db.execute("UPDATE jobs SET state=?, checkpoint_json=?, updated_at=? WHERE id=?",
                       (target, json.dumps(checkpoint), now, job_id))
            self._event(db, job_id, actor, "job.transition", {"from": current, "to": target, "reason": reason})
        return self.get_job(job_id)  # type: ignore[return-value]


    def save_checkpoint(self, job_id: str, checkpoint: dict[str, Any],
                        actor: str = "orchestrator") -> dict[str, Any]:
        """Persist resumable progress without allowing completed tasks to be undone.

        This records orchestration metadata only. It does not execute a task or
        independently prove that a task's output passed verification.
        """
        if not isinstance(checkpoint, dict):
            raise ValidationError("Checkpoint must be an object.")
        with _LOCK, self.connect() as db:
            row = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            if not row:
                raise ValidationError("Job does not exist.")
            job = self._decode_job(row)
            previous = job["checkpoint"]
            merged = {**previous, **checkpoint}
            task_ids = {task["id"] for task in job["tasks"]}

            completed = merged.get("completed_task_ids", [])
            if not isinstance(completed, list) or not all(isinstance(item, str) for item in completed):
                raise ValidationError("completed_task_ids must be a list of task IDs.")
            if len(completed) != len(set(completed)):
                raise ValidationError("completed_task_ids must not contain duplicates.")
            unknown = set(completed) - task_ids
            if unknown:
                raise ValidationError(f"Checkpoint contains unknown completed tasks: {sorted(unknown)}")
            previous_completed = set(previous.get("completed_task_ids", []))
            if not previous_completed.issubset(set(completed)):
                raise ValidationError("Checkpoint cannot remove previously completed tasks.")

            current_task = merged.get("current_task_id")
            if current_task is not None and current_task not in task_ids:
                raise ValidationError("current_task_id must refer to a task in this job.")
            merged["completed_task_ids"] = sorted(completed)
            if merged == previous:
                return job

            now = utc_now()
            db.execute("UPDATE jobs SET checkpoint_json=?, updated_at=? WHERE id=?",
                       (json.dumps(merged, sort_keys=True), now, job_id))
            self._event(db, job_id, actor, "job.checkpoint_saved", {
                "completed_task_ids": merged["completed_task_ids"],
                "current_task_id": merged.get("current_task_id"),
                "stage": merged.get("stage"),
            })
        return self.get_job(job_id)  # type: ignore[return-value]

    def events(self, job_id: str) -> list[dict[str, Any]]:
        with self.connect() as db:
            rows = db.execute("SELECT * FROM events WHERE job_id=? ORDER BY id", (job_id,)).fetchall()
        return [{"id": r["id"], "at": r["at"], "actor": r["actor"], "kind": r["kind"],
                 "payload": json.loads(r["payload_json"])} for r in rows]


def validate_task_graph(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not isinstance(tasks, list):
        raise ValidationError("Tasks must be a list.")
    ids: set[str] = set()
    normalized = []
    for task in tasks:
        if not isinstance(task, dict):
            raise ValidationError("Each task must be an object.")
        task_id, title = str(task.get("id", "")).strip(), str(task.get("title", "")).strip()
        requirements, depends = task.get("requirement_ids", []), task.get("depends_on", [])
        if not task_id or task_id in ids:
            raise ValidationError("Task IDs must be non-empty and unique.")
        if not title:
            raise ValidationError(f"Task {task_id} requires a title.")
        if not isinstance(requirements, list) or not all(isinstance(x, str) and x.strip() for x in requirements):
            raise ValidationError(f"Task {task_id} requirement_ids must be a list of non-empty strings.")
        if not isinstance(depends, list) or not all(isinstance(x, str) for x in depends):
            raise ValidationError(f"Task {task_id} depends_on must be a list of strings.")
        checks = task.get("acceptance_checks", [])
        if not isinstance(checks, list) or not all(isinstance(x, str) for x in checks):
            raise ValidationError(f"Task {task_id} acceptance_checks must be a list of strings.")
        ids.add(task_id)
        normalized.append({"id": task_id, "title": title, "requirement_ids": sorted(set(requirements)),
                           "depends_on": sorted(set(depends)), "acceptance_checks": checks})
    by_id = {task["id"]: task for task in normalized}
    for task in normalized:
        missing = set(task["depends_on"]) - ids
        if missing:
            raise ValidationError(f"Task {task['id']} has unknown dependencies: {sorted(missing)}")
        if task["id"] in task["depends_on"]:
            raise ValidationError(f"Task {task['id']} cannot depend on itself.")
    visiting: set[str] = set()
    visited: set[str] = set()
    def visit(task_id: str) -> None:
        if task_id in visiting:
            raise ValidationError("Task dependencies contain a cycle.")
        if task_id in visited:
            return
        visiting.add(task_id)
        for dep in by_id[task_id]["depends_on"]:
            visit(dep)
        visiting.remove(task_id)
        visited.add(task_id)
    for task_id in by_id:
        visit(task_id)
    return normalized


def ready_tasks(tasks: list[dict[str, Any]], completed: set[str] | None = None) -> list[dict[str, Any]]:
    completed = completed or set()
    return [t for t in tasks if t["id"] not in completed and set(t["depends_on"]) <= completed]


class ApiHandler(BaseHTTPRequestHandler):
    store: Store
    specs: Any

    def log_message(self, format: str, *args: Any) -> None:
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
        raw_length = self.headers.get("Content-Length", "0")
        try:
            length = int(raw_length)
        except (TypeError, ValueError) as exc:
            raise ValidationError("Content-Length must be a valid integer.") from exc
        if length < 1 or length > 1_000_000:
            raise ValidationError("Request body must be between 1 byte and 1 MB.")
        raw = self.rfile.read(length)
        if len(raw) != length:
            raise ValidationError("Request body ended before Content-Length bytes were received.")
        try:
            body = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ValidationError("Request body must contain valid UTF-8 JSON.") from exc
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
        if path == "/recovery/interrupted":
            return self._send(200, {
                "items": self.store.list_interrupted_jobs(),
                "automatic_resume": False,
                "note": "Candidates require operator review; worker ownership and task execution are not yet implemented.",
            })
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
            return self._send(200, {"items": self.store.events(parts[1])}
            )
        if len(parts) == 2 and parts[0] == "specifications":
            item = self.specs.get(parts[1])
            return self._send(200, item) if item else self._send(404, {"error": "Specification not found"})
        if len(parts) == 3 and parts[0] == "specifications" and parts[2] == "events":
            if not self.specs.get(parts[1]):
                return self._send(404, {"error": "Specification not found"})
            return self._send(200, {"items": self.specs.events(parts[1])})
        if len(parts) == 3 and parts[0] == "projects" and parts[2] == "specifications":
            if not self.store.get_project(parts[1]):
                return self._send(404, {"error": "Project not found"})
            return self._send(200, {"items": self.specs.list(parts[1])})
        return self._send(404, {"error": "Not found"})

    def do_POST(self) -> None:
        path = urlparse(self.path).path.rstrip("/")
        try:
            body = self._body()
            if path == "/projects":
                return self._send(201, self.store.create_project(body.get("name", ""), body.get("idea", "")))
            if path == "/jobs":
                return self._send(201, self.store.create_job(str(body.get("project_id", "")),
                    body.get("spec"), body.get("tasks"), body.get("budget")))
            parts = path.strip("/").split("/")
            if len(parts) == 3 and parts[0] == "jobs" and parts[2] == "transition":
                return self._send(200, self.store.transition(parts[1], str(body.get("target", "")),
                    actor="api-owner", reason=str(body.get("reason", ""))))
            if len(parts) == 3 and parts[0] == "jobs" and parts[2] == "checkpoint":
                if "checkpoint" not in body:
                    raise ValidationError("A checkpoint object is required.")
                return self._send(200, self.store.save_checkpoint(
                    parts[1], body["checkpoint"], actor="api-owner"))
            if len(parts) == 3 and parts[0] == "projects" and parts[2] == "specifications":
                return self._send(201, self.specs.save(parts[1], body))
            if len(parts) == 3 and parts[0] == "specifications" and parts[2] == "approve":
                return self._send(200, self.specs.approve(parts[1], actor="api-owner"))
            if len(parts) == 3 and parts[0] == "specifications" and parts[2] == "plan":
                spec = self.specs.get(parts[1])
                if not spec:
                    return self._send(404, {"error": "Specification not found"})
                if spec["status"] != "APPROVED":
                    raise ValidationError("Approve the specification before generating an execution plan.")
                from .specs import build_plan
                plan = build_plan(spec["spec"])
                try:
                    validated_plan = validate_task_graph(plan)
                except ValidationError:
                    raise
                return self._send(200, {"spec_id": spec["id"], "version": spec["version"],
                                        "tasks": validated_plan})
            return self._send(404, {"error": "Not found"})
        except (ValidationError, json.JSONDecodeError, TypeError) as exc:
            return self._send(400, {"error": str(exc)})
        except Exception as exc:
            # Keep the API response useful for debugging without logging request bodies or secrets.
            return self._send(500, {"error": f"Internal error: {type(exc).__name__}"})


def serve(host: str = "127.0.0.1", port: int = 8080, database: str = "data/factory.sqlite3") -> None:
    if host not in {"127.0.0.1", "localhost", "::1"} and os.environ.get("FACTORY_ALLOW_REMOTE") != "1":
        raise RuntimeError("Remote binding is disabled by default. Set FACTORY_ALLOW_REMOTE=1 only behind authenticated TLS.")
    from .specs import SpecStore, build_plan
    ApiHandler.build_plan = staticmethod(build_plan)
    ApiHandler.store = Store(database)
    ApiHandler.specs = SpecStore(ApiHandler.store)
    server = ThreadingHTTPServer((host, port), ApiHandler)
    print(f"AI Software Factory control plane listening on http://{host}:{port}")
    print(f"Database: {database}; agent execution: disabled")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
