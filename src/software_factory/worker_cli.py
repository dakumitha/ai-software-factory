"""Operator CLI commands for inspecting and stepping factory jobs.

Supports read-only inspection (list, status) and bounded one-step execution (step)
using explicitly allowlisted built-in task handlers under worker lease protection.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .artifact_task import handle_artifact_integrity_task
from .core import Store, ValidationError
from .execution import ExecutionController


def _job_summary(job: dict[str, Any], store: Store) -> dict[str, Any]:
    """Return operational metadata without exposing specification or task payloads."""
    tasks = job.get("tasks", [])
    checkpoint = job.get("checkpoint", {})
    completed = checkpoint.get("completed_task_ids", [])
    attempts = store.list_task_attempts(job["id"])
    return {
        "job_id": job["id"],
        "project_id": job["project_id"],
        "state": job["state"],
        "created_at": job["created_at"],
        "updated_at": job["updated_at"],
        "task_count": len(tasks),
        "completed_task_count": len(set(completed) & {task["id"] for task in tasks}),
        "task_attempt_count": len(attempts),
        "attempts_by_status": {
            status: sum(1 for attempt in attempts if attempt["status"] == status)
            for status in ("STARTED", "SUCCEEDED", "FAILED", "UNCERTAIN")
        },
    }


def main(argv: list[str] | None = None) -> int:
    """Run worker CLI commands; return a process exit code."""
    parser = argparse.ArgumentParser(
        description="Inspect and step AI Software Factory jobs."
    )
    parser.add_argument(
        "--database",
        default="data/factory.sqlite3",
        help="SQLite database path (default: data/factory.sqlite3).",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    list_parser = commands.add_parser("list", help="List jobs using safe summary fields.")
    list_parser.add_argument("--project-id", help="Limit results to one project.")

    status_parser = commands.add_parser("status", help="Inspect one job.")
    status_parser.add_argument("job_id", help="Job identifier.")

    step_parser = commands.add_parser("step", help="Execute one ready task for a running job under lease protection.")
    step_parser.add_argument("job_id", help="Job identifier.")
    step_parser.add_argument("--worker-id", default="cli-worker", help="Worker identifier (default: cli-worker).")
    step_parser.add_argument("--workspace", default="workspace", help="Workspace directory for task execution (default: workspace).")
    step_parser.add_argument("--ttl-seconds", type=int, default=60, help="Lease TTL in seconds (default: 60).")
    step_parser.add_argument("--enable-heartbeat", action="store_true", help="Enable background lease heartbeat.")
    step_parser.add_argument("--heartbeat-interval", type=float, default=15.0, help="Heartbeat interval in seconds (default: 15.0).")

    args = parser.parse_args(argv)

    store = Store(args.database)
    if args.command == "list":
        result = [_job_summary(job, store) for job in store.list_jobs(args.project_id)]
        print(json.dumps({"items": result, "count": len(result)}, indent=2, sort_keys=True))
        return 0

    if args.command == "status":
        job = store.get_job(args.job_id)
        if job is None:
            print(json.dumps({"error": "Job not found", "job_id": args.job_id}, sort_keys=True))
            return 2
        print(json.dumps(_job_summary(job, store), indent=2, sort_keys=True))
        return 0

    if args.command == "step":
        job = store.get_job(args.job_id)
        if job is None:
            print(json.dumps({"error": "Job not found", "job_id": args.job_id}, sort_keys=True))
            return 2

        if job["state"] != "RUNNING":
            print(json.dumps({
                "error": f"Job is not running (current state: {job['state']}). Only RUNNING jobs can execute tasks.",
                "job_id": args.job_id,
                "state": job["state"],
            }, indent=2, sort_keys=True))
            return 1

        workspace_path = Path(args.workspace)
        workspace_path.mkdir(parents=True, exist_ok=True)

        try:
            lease = store.acquire_lease(args.job_id, owner_id=args.worker_id, ttl_seconds=args.ttl_seconds)
        except ValidationError as exc:
            print(json.dumps({"error": f"Could not acquire lease: {exc}", "job_id": args.job_id}, sort_keys=True))
            return 1

        controller = ExecutionController(store)
        controller.register(
            "artifact_integrity",
            lambda payload: handle_artifact_integrity_task(workspace_path, payload["input"]),
        )

        try:
            res = controller.run_next(
                args.job_id,
                lease["token"],
                actor=args.worker_id,
                enable_heartbeat=args.enable_heartbeat,
                heartbeat_interval=args.heartbeat_interval,
            )
        finally:
            store.release_lease(args.job_id, lease["token"])

        output_summary = {
            "job_id": args.job_id,
            "status": res["status"],
            "task_id": res.get("task_id"),
            "attempt_id": res.get("attempt_id"),
            "error": res.get("error"),
            "outcome": res.get("outcome"),
            "completed_task_ids": res.get("completed_task_ids"),
        }
        print(json.dumps(output_summary, indent=2, sort_keys=True))
        if res["status"] == "TASK_FAILED":
            return 1
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
