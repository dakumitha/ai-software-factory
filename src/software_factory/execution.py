"""Deterministic, allowlisted task execution controller.

Only explicitly registered Python handlers execute. Task text is never interpreted
as code or a shell command. This module is a local prototype, not a sandbox.
"""
from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Callable

from .core import Store, ValidationError, ready_tasks
from .heartbeat import (
    HeartbeatKeeper,
    OUTCOME_HANDLER_ERROR,
    OUTCOME_OUTPUT_LIMIT_EXCEEDED,
    OUTCOME_SUCCESS,
    build_task_outcome,
)

TaskHandler = Callable[[dict[str, Any]], Any]


class ExecutionError(RuntimeError):
    """Task execution failed or was blocked by controller policy."""


class ExecutionController:
    def __init__(self, store: Store, handlers: dict[str, TaskHandler] | None = None):
        self.store = store
        self.handlers = dict(handlers or {})

    def register(self, task_type: str, handler: TaskHandler) -> None:
        if not isinstance(task_type, str) or not task_type.strip():
            raise ValueError("task_type must be a non-empty string")
        if not callable(handler):
            raise TypeError("handler must be callable")
        if task_type in self.handlers:
            raise ValueError(f"A handler is already registered for {task_type!r}")
        self.handlers[task_type] = handler

    @staticmethod
    def _input_for(task: dict[str, Any], job: dict[str, Any]) -> dict[str, Any]:
        payload = task.get("input", {})
        if not isinstance(payload, dict):
            raise ExecutionError(f"Task {task['id']} input must be an object")
        return {"task_id": task["id"], "title": task["title"],
                "input": payload, "spec": job["spec"]}

    def run_next(
        self,
        job_id: str,
        token: str,
        *,
        actor: str = "worker",
        enable_heartbeat: bool = False,
        heartbeat_interval: float = 15.0,
    ) -> dict[str, Any]:
        """Execute one ready task, or return a structured no-work/block result."""
        job = self.store.get_job(job_id)
        if not job:
            raise ExecutionError("Job does not exist")
        if job["state"] not in {"RUNNING", "VERIFYING"}:
            raise ExecutionError("Execution requires a RUNNING or VERIFYING job")

        checkpoint = job["checkpoint"]
        completed = set(checkpoint.get("completed_task_ids", []))
        tasks = job["tasks"]
        if completed == {task["id"] for task in tasks}:
            return {"status": "ALL_COMPLETE", "job_id": job_id, "task_id": None}

        ready = ready_tasks(tasks, completed)
        if not ready:
            return {"status": "NO_READY_TASK", "job_id": job_id, "task_id": None}

        task = sorted(ready, key=lambda item: item["id"])[0]
        task_type = task.get("type", "")
        handler = self.handlers.get(task_type)
        if handler is None:
            return {"status": "BLOCKED_HANDLER_MISSING", "job_id": job_id,
                    "task_id": task["id"], "task_type": task_type}

        payload = self._input_for(task, job)
        input_hash = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        key = f"{task['id']}:{input_hash}"
        attempt = self.store.start_task_attempt(job_id, task["id"], token, key, payload)
        if attempt["status"] != "STARTED":
            return {"status": "REVIEW_REQUIRED", "job_id": job_id, "task_id": task["id"],
                    "attempt_id": attempt["id"], "attempt_status": attempt["status"],
                    "reason": "Existing attempt is terminal; controller will not replay it automatically."}

        t0 = time.perf_counter()
        try:
            if enable_heartbeat:
                with HeartbeatKeeper(self.store, job_id, token, interval_seconds=heartbeat_interval):
                    output = handler(payload)
            else:
                output = handler(payload)
            duration_ms = int((time.perf_counter() - t0) * 1000)
            encoded = json.dumps(output, sort_keys=True, ensure_ascii=False)
            if len(encoded.encode("utf-8")) > 1_000_000:
                raise ExecutionError("Handler output exceeds the 1 MB limit")
        except Exception as exc:
            duration_ms = int((time.perf_counter() - t0) * 1000)
            cat = (
                OUTCOME_OUTPUT_LIMIT_EXCEEDED
                if isinstance(exc, ExecutionError) and "1 MB" in str(exc)
                else OUTCOME_HANDLER_ERROR
            )
            outcome = build_task_outcome(
                category=cat,
                duration_ms=duration_ms,
                task_id=task["id"],
                attempt_id=attempt["id"],
                error=f"{type(exc).__name__}: {exc}",
            )
            self.store.finish_task_attempt(job_id, attempt["id"], token, "FAILED",
                                           error=f"{type(exc).__name__}: {exc}")
            return {"status": "TASK_FAILED", "job_id": job_id, "task_id": task["id"],
                    "attempt_id": attempt["id"], "error_type": type(exc).__name__,
                    "error": str(exc)[:1000], "outcome": outcome}

        finished = self.store.finish_task_attempt(job_id, attempt["id"], token, "SUCCEEDED", output=output)
        outcome = build_task_outcome(
            category=OUTCOME_SUCCESS,
            duration_ms=duration_ms,
            task_id=task["id"],
            attempt_id=attempt["id"],
        )
        updated = self.store.save_checkpoint(job_id, {
            "completed_task_ids": sorted(completed | {task["id"]}),
            "current_task_id": None,
            "last_attempt_id": attempt["id"],
            "last_task_output": output,
        }, actor=actor)
        return {"status": "TASK_SUCCEEDED", "job_id": job_id, "task_id": task["id"],
                "attempt_id": attempt["id"], "attempt_status": finished["status"],
                "output": output, "completed_task_ids": updated["checkpoint"]["completed_task_ids"],
                "outcome": outcome}
