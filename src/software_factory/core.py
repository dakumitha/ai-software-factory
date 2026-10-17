"""Durable, dependency-free control plane for software-factory jobs."""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import sqlite3
import threading
import uuid
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from .api_registry import ApiRegistry, RegistryError

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


class ClosableConnection(sqlite3.Connection):
    """A SQLite connection that automatically commits/rolls back and closes upon context exit.

    Standard library sqlite3.Connection context manager only manages transactions,
    leaving the underlying connection open until garbage collection. This causes file locking
    and PermissionErrors on Windows, and emits ResourceWarning in Python 3.13+.
    """

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            return super().__exit__(exc_type, exc_val, exc_tb)
        finally:
            self.close()


class Store:
    def __init__(self, path: str | Path = "data/factory.sqlite3"):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=10, factory=ClosableConnection)
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
            latest_known = 4
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

            if 3 not in applied:
                db.execute("""
                    CREATE TABLE IF NOT EXISTS job_leases (
                        job_id TEXT PRIMARY KEY,
                        owner_id TEXT NOT NULL,
                        token_hash TEXT NOT NULL,
                        acquired_at TEXT NOT NULL,
                        heartbeat_at TEXT NOT NULL,
                        expires_at TEXT NOT NULL,
                        FOREIGN KEY(job_id) REFERENCES jobs(id)
                    )
                """)
                db.execute("CREATE INDEX IF NOT EXISTS idx_job_leases_expires_at ON job_leases(expires_at)")
                db.execute(
                    "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                    (3, utc_now()),
                )

            if 4 not in applied:
                db.execute("""
                    CREATE TABLE IF NOT EXISTS task_attempts (
                        id TEXT PRIMARY KEY,
                        job_id TEXT NOT NULL,
                        task_id TEXT NOT NULL,
                        attempt_number INTEGER NOT NULL,
                        idempotency_key TEXT NOT NULL,
                        input_hash TEXT NOT NULL,
                        status TEXT NOT NULL CHECK(status IN ('STARTED', 'SUCCEEDED', 'FAILED', 'UNCERTAIN')),
                        output_json TEXT,
                        error_text TEXT,
                        started_at TEXT NOT NULL,
                        finished_at TEXT,
                        UNIQUE(job_id, idempotency_key),
                        UNIQUE(job_id, task_id, attempt_number),
                        FOREIGN KEY(job_id) REFERENCES jobs(id)
                    )
                """)
                db.execute("CREATE INDEX IF NOT EXISTS idx_task_attempts_job_status ON task_attempts(job_id, status)")
                db.execute(
                    "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                    (4, utc_now()),
                )

    def schema_version(self) -> int:
        """Return the highest successfully recorded schema migration."""
        with self.connect() as db:
            row = db.execute("SELECT MAX(version) AS version FROM schema_migrations").fetchone()
        return int(row["version"] or 0)

    @staticmethod
    def _validate_lease_ttl(ttl_seconds: int) -> int:
        if isinstance(ttl_seconds, bool) or not isinstance(ttl_seconds, int) or not 10 <= ttl_seconds <= 3600:
            raise ValidationError("Lease TTL must be an integer between 10 and 3600 seconds.")
        return ttl_seconds

    def acquire_lease(self, job_id: str, owner_id: str, ttl_seconds: int = 60) -> dict[str, Any]:
        """Acquire a time-limited worker lease and return its secret token once."""
        ttl_seconds = self._validate_lease_ttl(ttl_seconds)
        owner_id = owner_id.strip() if isinstance(owner_id, str) else ""
        if not owner_id:
            raise ValidationError("owner_id is required.")
        now_dt = datetime.now(timezone.utc)
        now = now_dt.isoformat(timespec="seconds")
        expires = (now_dt + timedelta(seconds=ttl_seconds)).isoformat(timespec="seconds")
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        with _LOCK, self.connect() as db:
            job = db.execute("SELECT state FROM jobs WHERE id=?", (job_id,)).fetchone()
            if not job:
                raise ValidationError("Job does not exist.")
            if job["state"] not in {"RUNNING", "VERIFYING"}:
                raise ValidationError("A worker lease can only be acquired for RUNNING or VERIFYING jobs.")
            lease = db.execute("SELECT * FROM job_leases WHERE job_id=?", (job_id,)).fetchone()
            if lease and lease["expires_at"] > now:
                raise ValidationError("Job already has an active worker lease.")
            db.execute("""INSERT INTO job_leases(job_id, owner_id, token_hash, acquired_at, heartbeat_at, expires_at)
                VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(job_id) DO UPDATE SET
                owner_id=excluded.owner_id, token_hash=excluded.token_hash, acquired_at=excluded.acquired_at,
                heartbeat_at=excluded.heartbeat_at, expires_at=excluded.expires_at""",
                (job_id, owner_id, token_hash, now, now, expires))
            self._event(db, job_id, owner_id, "job.lease_acquired", {"expires_at": expires})
        return {"job_id": job_id, "owner_id": owner_id, "token": token,
                "acquired_at": now, "heartbeat_at": now, "expires_at": expires}

    def heartbeat_lease(self, job_id: str, token: str, ttl_seconds: int = 60) -> dict[str, Any]:
        """Extend a lease only when the supplied secret still owns an unexpired lease."""
        ttl_seconds = self._validate_lease_ttl(ttl_seconds)
        now_dt = datetime.now(timezone.utc)
        now = now_dt.isoformat(timespec="seconds")
        expires = (now_dt + timedelta(seconds=ttl_seconds)).isoformat(timespec="seconds")
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest() if isinstance(token, str) else ""
        with _LOCK, self.connect() as db:
            lease = db.execute("SELECT * FROM job_leases WHERE job_id=?", (job_id,)).fetchone()
            if not lease or lease["expires_at"] <= now or not secrets.compare_digest(lease["token_hash"], token_hash):
                raise ValidationError("Lease is missing, expired, or the token is invalid.")
            db.execute("UPDATE job_leases SET heartbeat_at=?, expires_at=? WHERE job_id=?", (now, expires, job_id))
            self._event(db, job_id, lease["owner_id"], "job.lease_heartbeat", {"expires_at": expires})
            return {"job_id": job_id, "owner_id": lease["owner_id"],
                    "heartbeat_at": now, "expires_at": expires}

    def release_lease(self, job_id: str, token: str) -> None:
        """Release a lease only when the supplied secret matches its current owner token."""
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest() if isinstance(token, str) else ""
        with _LOCK, self.connect() as db:
            lease = db.execute("SELECT * FROM job_leases WHERE job_id=?", (job_id,)).fetchone()
            if not lease or not secrets.compare_digest(lease["token_hash"], token_hash):
                raise ValidationError("Lease is missing or the token is invalid.")
            db.execute("DELETE FROM job_leases WHERE job_id=?", (job_id,))
            self._event(db, job_id, lease["owner_id"], "job.lease_released", {})

    def get_lease(self, job_id: str) -> dict[str, Any] | None:
        """Return the current lease record for a job, omitting secret token hashes."""
        with self.connect() as db:
            lease = db.execute("SELECT * FROM job_leases WHERE job_id=?", (job_id,)).fetchone()
        if not lease:
            return None
        return {
            "job_id": lease["job_id"],
            "owner_id": lease["owner_id"],
            "acquired_at": lease["acquired_at"],
            "heartbeat_at": lease["heartbeat_at"],
            "expires_at": lease["expires_at"],
        }

    def revoke_expired_lease(self, job_id: str, actor: str = "recovery", reason: str = "",
                             now: str | None = None, force: bool = False) -> dict[str, Any] | None:
        """Revoke a lease that has expired, or return None if no lease exists.

        An active, unexpired lease cannot be revoked unless force=True is explicitly passed
        under authorized operator policy.
        """
        current_ts = now or utc_now()
        with _LOCK, self.connect() as db:
            lease = db.execute("SELECT * FROM job_leases WHERE job_id=?", (job_id,)).fetchone()
            if not lease:
                return None
            if lease["expires_at"] > current_ts and not force:
                raise ValidationError("Cannot revoke an active, unexpired lease without explicit revocation authority.")
            db.execute("DELETE FROM job_leases WHERE job_id=?", (job_id,))
            prior = {
                "job_id": lease["job_id"],
                "owner_id": lease["owner_id"],
                "acquired_at": lease["acquired_at"],
                "heartbeat_at": lease["heartbeat_at"],
                "expires_at": lease["expires_at"],
            }
            self._event(db, job_id, actor, "job.lease_revoked", {
                "prior_owner_id": lease["owner_id"],
                "expired_at": lease["expires_at"],
                "reason": reason or "Lease expired without renewal; revoked by recovery policy.",
            })
            return prior

    def mark_attempt_interrupted(self, job_id: str, attempt_id: str,
                                 actor: str = "recovery", reason: str = "",
                                 now: str | None = None) -> dict[str, Any]:
        """Mark a STARTED attempt as UNCERTAIN after a crash, timeout, or expired lease.

        Terminal attempts (SUCCEEDED, FAILED, UNCERTAIN) cannot be altered.
        An attempt left in STARTED is uncertain because side effects may or may not have occurred.
        """
        current_ts = now or utc_now()
        with _LOCK, self.connect() as db:
            row = db.execute("SELECT * FROM task_attempts WHERE id=? AND job_id=?",
                             (attempt_id, job_id)).fetchone()
            if not row:
                raise ValidationError("Task attempt does not exist for this job.")
            if row["status"] != "STARTED":
                raise ValidationError("Only STARTED task attempts can be marked interrupted.")
            explanation = reason or "Attempt interrupted by worker crash, timeout, or lease expiry."
            db.execute(
                "UPDATE task_attempts SET status='UNCERTAIN', error_text=?, finished_at=? WHERE id=?",
                (explanation[:4000], current_ts, attempt_id),
            )
            self._event(db, job_id, actor, "task.attempt_interrupted", {
                "attempt_id": attempt_id,
                "task_id": row["task_id"],
                "status": "UNCERTAIN",
                "reason": explanation,
            })
        return self.get_task_attempt(job_id, attempt_id)  # type: ignore[return-value]

    @staticmethod
    def _lease_for_worker(db: sqlite3.Connection, job_id: str, token: str) -> sqlite3.Row:
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest() if isinstance(token, str) else ""
        lease = db.execute("SELECT * FROM job_leases WHERE job_id=?", (job_id,)).fetchone()
        if (not lease or lease["expires_at"] <= utc_now()
                or not secrets.compare_digest(lease["token_hash"], token_hash)):
            raise ValidationError("A valid, unexpired worker lease is required.")
        return lease

    def start_task_attempt(self, job_id: str, task_id: str, token: str,
                           idempotency_key: str, input_data: Any = None) -> dict[str, Any]:
        """Record a task attempt before execution, protected by an active worker lease.

        Reusing a key with the same task/input returns the original attempt.
        Reusing it for different work is rejected. A STARTED attempt found after a
        crash must be treated as uncertain, not automatically repeated.
        """
        if not isinstance(idempotency_key, str) or not idempotency_key.strip() or len(idempotency_key) > 200:
            raise ValidationError("idempotency_key must be a non-empty string of at most 200 characters.")
        if not isinstance(task_id, str) or not task_id.strip():
            raise ValidationError("task_id is required.")
        input_hash = hashlib.sha256(json.dumps(input_data, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        with _LOCK, self.connect() as db:
            lease = self._lease_for_worker(db, job_id, token)
            row = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            if not row:
                raise ValidationError("Job does not exist.")
            if row["state"] not in {"RUNNING", "VERIFYING"}:
                raise ValidationError("Task attempts require a RUNNING or VERIFYING job.")
            task_ids = {task["id"] for task in json.loads(row["tasks_json"])}
            if task_id not in task_ids:
                raise ValidationError("Task does not belong to this job.")
            existing = db.execute(
                "SELECT * FROM task_attempts WHERE job_id=? AND idempotency_key=?",
                (job_id, idempotency_key.strip()),
            ).fetchone()
            if existing:
                if existing["task_id"] != task_id or existing["input_hash"] != input_hash:
                    raise ValidationError("Idempotency key was already used for different task input.")
                item = dict(existing)
                item["output"] = json.loads(item.pop("output_json")) if item.get("output_json") else None
                return item
            number = db.execute(
                "SELECT COALESCE(MAX(attempt_number), 0) + 1 AS n FROM task_attempts WHERE job_id=? AND task_id=?",
                (job_id, task_id),
            ).fetchone()["n"]
            attempt_id, now = new_id("attempt"), utc_now()
            db.execute("""INSERT INTO task_attempts
                (id, job_id, task_id, attempt_number, idempotency_key, input_hash, status, started_at)
                VALUES (?, ?, ?, ?, ?, ?, 'STARTED', ?)""",
                (attempt_id, job_id, task_id, number, idempotency_key.strip(), input_hash, now))
            self._event(db, job_id, lease["owner_id"], "task.attempt_started",
                        {"attempt_id": attempt_id, "task_id": task_id, "attempt_number": number})
            result = db.execute("SELECT * FROM task_attempts WHERE id=?", (attempt_id,)).fetchone()
            item = dict(result)
            item["output"] = None
            return item

    def finish_task_attempt(self, job_id: str, attempt_id: str, token: str,
                            status: str, output: Any = None, error: str = "") -> dict[str, Any]:
        """Finish a task attempt under its active lease; terminal results are immutable."""
        if status not in {"SUCCEEDED", "FAILED", "UNCERTAIN"}:
            raise ValidationError("Attempt status must be SUCCEEDED, FAILED, or UNCERTAIN.")
        with _LOCK, self.connect() as db:
            lease = self._lease_for_worker(db, job_id, token)
            row = db.execute("SELECT * FROM task_attempts WHERE id=? AND job_id=?",
                             (attempt_id, job_id)).fetchone()
            if not row:
                raise ValidationError("Task attempt does not exist for this job.")
            if row["status"] != "STARTED":
                if row["status"] == status:
                    return self.get_task_attempt(job_id, attempt_id)  # type: ignore[return-value]
                raise ValidationError("A finished task attempt cannot be changed.")
            now = utc_now()
            output_json = json.dumps(output, sort_keys=True) if status == "SUCCEEDED" and output is not None else None
            error_text = str(error)[:4000] if status != "SUCCEEDED" else None
            db.execute("""UPDATE task_attempts SET status=?, output_json=?, error_text=?, finished_at=?
                          WHERE id=?""", (status, output_json, error_text, now, attempt_id))
            self._event(db, job_id, lease["owner_id"], "task.attempt_finished",
                        {"attempt_id": attempt_id, "task_id": row["task_id"], "status": status})
        return self.get_task_attempt(job_id, attempt_id)  # type: ignore[return-value]

    def get_task_attempt(self, job_id: str, attempt_id: str) -> dict[str, Any] | None:
        with self.connect() as db:
            row = db.execute("SELECT * FROM task_attempts WHERE id=? AND job_id=?",
                             (attempt_id, job_id)).fetchone()
        if not row:
            return None
        item = dict(row)
        item["output"] = json.loads(item.pop("output_json")) if item.get("output_json") else None
        return item

    def list_task_attempts(self, job_id: str) -> list[dict[str, Any]]:
        with self.connect() as db:
            rows = db.execute("SELECT * FROM task_attempts WHERE job_id=? ORDER BY started_at, attempt_number",
                              (job_id,)).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["output"] = json.loads(item.pop("output_json")) if item.get("output_json") else None
            result.append(item)
        return result

    def list_interrupted_jobs(self) -> list[dict[str, Any]]:
        """List jobs left in active execution states for explicit recovery review.

        This is intentionally observational: without worker leases/heartbeats,
        the store cannot safely decide whether another process still owns a job.
        """
        now = utc_now()
        with self.connect() as db:
            rows = db.execute(
                """SELECT jobs.*, job_leases.owner_id AS lease_owner,
                          job_leases.expires_at AS lease_expires_at
                   FROM jobs LEFT JOIN job_leases ON job_leases.job_id=jobs.id
                   WHERE jobs.state IN ('RUNNING', 'VERIFYING')
                   ORDER BY jobs.updated_at ASC, jobs.id ASC"""
            ).fetchall()
        candidates = []
        for row in rows:
            if row["lease_expires_at"] and row["lease_expires_at"] > now:
                continue
            job = self._decode_job(row)
            checkpoint = job["checkpoint"]
            with self.connect() as db:
                uncertain_count = db.execute(
                    "SELECT COUNT(*) FROM task_attempts WHERE job_id=? AND status IN ('STARTED', 'UNCERTAIN')",
                    (job["id"],),
                ).fetchone()[0]
            candidates.append({
                "uncertain_attempt_count": uncertain_count,
                "job_id": job["id"],
                "project_id": job["project_id"],
                "state": job["state"],
                "updated_at": job["updated_at"],
                "current_task_id": checkpoint.get("current_task_id"),
                "completed_task_ids": checkpoint.get("completed_task_ids", []),
                "lease_status": "expired" if row["lease_expires_at"] else "missing",
                "lease_owner": row["lease_owner"],
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
        task_type = task.get("type", "")
        task_input = task.get("input", {})
        if not isinstance(task_type, str):
            raise ValidationError(f"Task {task_id} type must be a string.")
        if not isinstance(task_input, dict):
            raise ValidationError(f"Task {task_id} input must be an object.")
        if not isinstance(checks, list) or not all(isinstance(x, str) for x in checks):
            raise ValidationError(f"Task {task_id} acceptance_checks must be a list of strings.")
        ids.add(task_id)
        normalized.append({"id": task_id, "title": title, "type": task_type.strip(), "input": task_input,
                           "requirement_ids": sorted(set(requirements)), "depends_on": sorted(set(depends)),
                           "acceptance_checks": checks})
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
    api_registry: Any

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
        parsed_url = urlparse(self.path)
        path = parsed_url.path.rstrip("/") or "/"
        query_params = parse_qs(parsed_url.query)
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
        if path == "/api-candidates":
            try:
                items = self.api_registry.list(
                    query=query_params.get("query", [""])[0],
                    category=query_params.get("category", [""])[0],
                    approval_status=query_params.get("status", [""])[0],
                )
            except RegistryError as exc:
                return self._send(400, {"error": str(exc)})
            return self._send(200, {"items": items})
        if path == "/api-candidates/events":
            return self._send(200, {"items": self.api_registry.events()})
        parts = path.strip("/").split("/")
        if len(parts) == 2 and parts[0] == "api-candidates":
            try:
                candidate_id = int(parts[1])
            except ValueError:
                return self._send(400, {"error": "Candidate ID must be an integer."})
            candidate = self.api_registry.get(candidate_id)
            return self._send(200, candidate) if candidate else self._send(404, {"error": "API candidate not found"})
        if len(parts) == 3 and parts[0] == "api-candidates" and parts[2] == "events":
            try:
                candidate_id = int(parts[1])
            except ValueError:
                return self._send(400, {"error": "Candidate ID must be an integer."})
            if not self.api_registry.get(candidate_id):
                return self._send(404, {"error": "API candidate not found"})
            return self._send(200, {"items": self.api_registry.events(candidate_id)})
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
            if path == "/api-candidates":
                item = self.api_registry.add(
                    body.get("name", ""), body.get("category", ""), body.get("source_url", ""),
                    provider_url=body.get("provider_url", ""),
                    pricing_status=body.get("pricing_status", "UNKNOWN"),
                    licence_status=body.get("licence_status", "UNKNOWN"),
                    notes=body.get("notes", ""), actor="api-owner",
                )
                return self._send(201, item)
            if path == "/projects":
                return self._send(201, self.store.create_project(body.get("name", ""), body.get("idea", "")))
            if path == "/jobs":
                return self._send(201, self.store.create_job(str(body.get("project_id", "")),
                    body.get("spec"), body.get("tasks"), body.get("budget")))
            parts = path.strip("/").split("/")
            if len(parts) == 3 and parts[0] == "api-candidates" and parts[2] in {"review", "decision"}:
                try:
                    candidate_id = int(parts[1])
                except ValueError:
                    raise ValidationError("Candidate ID must be an integer.")
                if not self.api_registry.get(candidate_id):
                    return self._send(404, {"error": "API candidate not found"})
                if parts[2] == "review":
                    item = self.api_registry.review(
                        candidate_id,
                        verification_status=str(body.get("verification_status", "UNVERIFIED")),
                        licence_status=str(body.get("licence_status", "UNKNOWN")),
                        pricing_status=str(body.get("pricing_status", "UNKNOWN")),
                        notes=body.get("notes", ""), actor="api-owner",
                    )
                else:
                    item = self.api_registry.decide(
                        candidate_id, str(body.get("approval_status", "")),
                        reason=body.get("reason", ""), actor="api-owner",
                    )
                return self._send(200, item)
            if len(parts) == 3 and parts[0] == "jobs" and parts[2] == "transition":
                return self._send(200, self.store.transition(parts[1], str(body.get("target", "")),
                    actor="api-owner", reason=str(body.get("reason", ""))))
            if len(parts) == 3 and parts[0] == "jobs" and parts[2] == "checkpoint":
                if "checkpoint" not in body:
                    raise ValidationError("A checkpoint object is required.")
                return self._send(200, self.store.save_checkpoint(
                    parts[1], body["checkpoint"], actor="api-owner"))
            if len(parts) == 3 and parts[0] == "jobs" and parts[2] == "task-attempts":
                item = self.store.start_task_attempt(parts[1], str(body.get("task_id", "")),
                    body.get("token", ""), body.get("idempotency_key", ""), body.get("input"))
                return self._send(200, item)
            if len(parts) == 4 and parts[0] == "jobs" and parts[2] == "task-attempts":
                item = self.store.finish_task_attempt(parts[1], parts[3], body.get("token", ""),
                    str(body.get("status", "")), body.get("output"), str(body.get("error", "")))
                return self._send(200, item)
            if len(parts) == 3 and parts[0] == "jobs" and parts[2] == "lease":
                lease = self.store.acquire_lease(parts[1], str(body.get("owner_id", "")),
                    body.get("ttl_seconds", 60))
                return self._send(201, lease)
            if len(parts) == 4 and parts[0] == "jobs" and parts[2:] == ["lease", "heartbeat"]:
                return self._send(200, self.store.heartbeat_lease(parts[1], body.get("token", ""),
                    body.get("ttl_seconds", 60)))
            if len(parts) == 4 and parts[0] == "jobs" and parts[2:] == ["lease", "release"]:
                self.store.release_lease(parts[1], body.get("token", ""))
                return self._send(200, {"released": True, "job_id": parts[1]})
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
        except (ValidationError, RegistryError, json.JSONDecodeError, TypeError) as exc:
            return self._send(400, {"error": str(exc)})
        except Exception as exc:
            # Keep the API response useful for debugging without logging request bodies or secrets.
            return self._send(500, {"error": f"Internal error: {type(exc).__name__}"})


def serve(host: str = "127.0.0.1", port: int = 8080, database: str = "data/factory.sqlite3") -> None:
    if host not in {"127.0.0.1", "localhost", "::1"} and os.environ.get("FACTORY_ALLOW_REMOTE") != "1":
        raise RuntimeError("Remote binding is disabled by default. Set FACTORY_ALLOW_REMOTE=1 only behind authenticated TLS.")
    from .specs import SpecStore, build_plan
    from .api_registry import ApiRegistry
    ApiHandler.build_plan = staticmethod(build_plan)
    ApiHandler.store = Store(database)
    ApiHandler.specs = SpecStore(ApiHandler.store)
    ApiHandler.api_registry = ApiRegistry(database)
    server = ThreadingHTTPServer((host, port), ApiHandler)
    print(f"AI Software Factory control plane listening on http://{host}:{port}")
    print(f"Database: {database}; agent execution: disabled")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
