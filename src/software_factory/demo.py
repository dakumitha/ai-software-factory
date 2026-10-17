"""Run a disposable, zero-cost demonstration of the factory control plane.

This is deliberately a dry run: it exercises specification approval, planning,
job state transitions, worker leases, task attempts, and checkpoints. It does not
generate source code, call an AI provider, execute shell commands, or claim that
the planned acceptance criteria have passed.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from .core import Store
from .execution import ExecutionController
from .specs import SpecStore, build_plan


def run_demo() -> dict[str, Any]:
    """Run a complete deterministic orchestration demo in a temporary database."""
    specification = {
        "title": "Demo task tracker",
        "goal": "Demonstrate traceable planning without external services.",
        "requirements": [
            {
                "id": "DEMO-REQ-001",
                "description": "Record a task",
                "priority": "must",
                "acceptance_criteria": ["A task record contains a title."],
            },
            {
                "id": "DEMO-REQ-002",
                "description": "Track task completion",
                "priority": "must",
                "acceptance_criteria": ["A task record can represent completion state."],
            },
        ],
        "open_questions": [],
        "assumptions": ["This run demonstrates orchestration only."],
        "constraints": ["No network, AI provider, shell, or generated code execution."],
    }

    # A temporary directory ensures the example leaves no demo records in the
    # user's normal database and can be safely rerun without cleanup.
    with tempfile.TemporaryDirectory(prefix="ai-software-factory-demo-") as temp_dir:
        store = Store(Path(temp_dir) / "demo.sqlite3")
        project = store.create_project(
            "Disposable control-plane demo", specification["goal"]
        )
        spec_store = SpecStore(store)
        saved_spec = spec_store.save(project["id"], specification)
        approved_spec = spec_store.approve(saved_spec["id"], actor="demo-owner")
        plan = build_plan(approved_spec["spec"])

        # The demo handler only records which planned task was reached. It does
        # not pretend to implement the requirement or pass its acceptance tests.
        demo_tasks = [
            {
                **task,
                "type": "demo_record",
                "input": {"acceptance_checks": task["acceptance_checks"]},
            }
            for task in plan
        ]
        job = store.create_job(
            project["id"],
            spec=approved_spec["spec"],
            tasks=demo_tasks,
            budget={"max_agent_calls": 0, "max_runtime_seconds": 0},
        )
        for state in ("SPEC_READY", "PLAN_READY", "AWAITING_APPROVAL", "QUEUED", "RUNNING"):
            store.transition(job["id"], state, actor="demo", reason="deterministic demo")

        lease = store.acquire_lease(job["id"], owner_id="demo-worker", ttl_seconds=60)

        def record_demo_task(payload: dict[str, Any]) -> dict[str, Any]:
            return {
                "demo_only": True,
                "task_id": payload["task_id"],
                "planned_acceptance_check_count": len(
                    payload["input"].get("acceptance_checks", [])
                ),
                "note": "Recorded as a dry run; acceptance checks were not executed.",
            }

        controller = ExecutionController(store, {"demo_record": record_demo_task})
        task_results = []
        try:
            for _ in range(len(demo_tasks) + 1):
                result = controller.run_next(job["id"], lease["token"], actor="demo-worker")
                task_results.append(result)
                if result["status"] == "ALL_COMPLETE":
                    break
                if result["status"] != "TASK_SUCCEEDED":
                    raise RuntimeError(f"Demo stopped safely: {result['status']}")
            else:
                raise RuntimeError("Demo exceeded its bounded task-step limit.")
        finally:
            store.release_lease(job["id"], lease["token"])

        store.transition(job["id"], "VERIFYING", actor="demo", reason="dry-run orchestration finished")
        # The demo has no independent verifier, so it stops at human review and
        # never promotes the job to RELEASE_READY or RELEASED.
        store.transition(
            job["id"], "REVIEW_REQUIRED",
            actor="demo",
            reason="dry-run completed; implementation and acceptance tests remain unverified",
        )
        final_job = store.get_job(job["id"])
        return {
            "demo_mode": "deterministic_dry_run",
            "external_network_calls": 0,
            "ai_provider_calls": 0,
            "shell_commands_executed": 0,
            "project_created": True,
            "specification_status": approved_spec["status"],
            "planned_task_count": len(demo_tasks),
            "successful_demo_task_count": sum(
                result["status"] == "TASK_SUCCEEDED" for result in task_results
            ),
            "completed_task_ids": final_job["checkpoint"].get("completed_task_ids", []),
            "final_job_state": final_job["state"],
            "release_performed": False,
            "limitations": [
                "No source code was generated or executed.",
                "Acceptance criteria were recorded, not tested.",
                "The result is not evidence of production readiness.",
            ],
        }


def main() -> None:
    """Print the dry-run report as JSON for easy reading or piping."""
    print(json.dumps(run_demo(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
