"""Read-only operator commands for inspecting persisted factory jobs.

This CLI deliberately does not acquire leases, execute tasks, or print task
inputs, outputs, lease tokens, or other potentially sensitive payloads.
"""
from __future__ import annotations

import argparse
import json
from typing import Any

from .core import Store


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
    """Run read-only job inspection commands; return a process exit code."""
    parser = argparse.ArgumentParser(
        description="Inspect AI Software Factory jobs without executing tasks."
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
    args = parser.parse_args(argv)

    store = Store(args.database)
    if args.command == "list":
        result = [_job_summary(job, store) for job in store.list_jobs(args.project_id)]
        print(json.dumps({"items": result, "count": len(result)}, indent=2, sort_keys=True))
        return 0

    job = store.get_job(args.job_id)
    if job is None:
        print(json.dumps({"error": "Job not found", "job_id": args.job_id}, sort_keys=True))
        return 2
    print(json.dumps(_job_summary(job, store), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
