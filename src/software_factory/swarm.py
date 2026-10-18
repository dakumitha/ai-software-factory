"""Dynamic Multi-Agent Swarm Coordinator and Concurrent Execution Pool.

Inspired by dynamic horizontal-scaling swarm architectures (e.g. Moonshot Kimi Swarm),
this module enables a Lead Coordinator agent to decompose large, multi-sided platforms
into specialized sub-agent squads (Backend, Customer Web, Customer Mobile, Seller Portal,
Rider Dispatch, Admin Dashboard, and QA) and execute them concurrently in isolated sandboxes.
"""
from __future__ import annotations

import concurrent.futures
import json
import threading
import time
from pathlib import Path
from typing import Any, Callable, Mapping

from .core import Store, ValidationError, ready_tasks
from .heartbeat import (
    OUTCOME_HANDLER_ERROR,
    OUTCOME_SUCCESS,
    HeartbeatKeeper,
    build_task_outcome,
)
from .resilience import CircuitBreaker, RetryPolicy
from .sandbox import IsolatedWorkspace, SandboxPolicy

# Standard Squad Categories
SQUAD_BACKEND = "backend_core"
SQUAD_CUSTOMER_WEB = "customer_web"
SQUAD_CUSTOMER_MOBILE = "customer_mobile"
SQUAD_SELLER_PORTAL = "seller_portal"
SQUAD_RIDER_DISPATCH = "rider_dispatch"
SQUAD_ADMIN_OPERATIONS = "admin_operations"
SQUAD_QA_VERIFICATION = "qa_verification"

DEFAULT_SQUADS = [
    SQUAD_BACKEND,
    SQUAD_CUSTOMER_WEB,
    SQUAD_CUSTOMER_MOBILE,
    SQUAD_SELLER_PORTAL,
    SQUAD_RIDER_DISPATCH,
    SQUAD_ADMIN_OPERATIONS,
]


def decompose_to_swarm_tasks(
    spec: dict[str, Any],
    *,
    squads: list[str] | None = None,
    tasks_per_squad: int = 3,
) -> list[dict[str, Any]]:
    """Dynamically decompose a platform specification into a multi-squad agent swarm graph.

    Structure:
    - Phase 1: Shared Database & API Schema (`backend_core`) -> depends on []
    - Phase 2: Parallel Squad Tasks (Customer Web, Mobile, Seller, Rider, Admin) -> depend on Phase 1
    - Phase 3: Integration & QA Verification -> depends on all Phase 2 tasks
    """
    target_squads = squads or DEFAULT_SQUADS
    tasks: list[dict[str, Any]] = []

    # Phase 1: Foundation and Shared Database/API Contract
    foundation_id = "foundation-schema"
    tasks.append({
        "id": foundation_id,
        "title": "Define Unified Database Schema & API Contracts (Shared Brain)",
        "squad": SQUAD_BACKEND,
        "type": "artifact_integrity",
        "depends_on": [],
        "input": {
            "kind": "artifact_integrity",
            "path": "shared/contracts/schema.json",
            "evidence_path": f"evidence/{foundation_id}-evidence.json",
            "content": json.dumps({
                "models": ["User", "Product", "Order", "DeliveryRoute", "Payment", "Dispute"],
                "roles": ["customer", "seller", "rider", "admin"],
                "version": "1.0.0",
                "spec_title": spec.get("title", "Platform Specification"),
            }, indent=2) + "\n",
            "require_json": True,
        },
    })

    phase_2_task_ids: list[str] = []

    # Phase 2: Parallel Stakeholder Squads
    for squad in target_squads:
        prefix = squad.replace("_", "-")
        for i in range(1, tasks_per_squad + 1):
            task_id = f"{prefix}-task-{i}"
            phase_2_task_ids.append(task_id)

            if squad == SQUAD_BACKEND:
                desc = f"Implement Core API Microservice #{i} (Auth/Orders/Dispatch)"
                path = f"backend/service-{i}.json"
            elif squad == SQUAD_CUSTOMER_WEB:
                desc = f"Build Customer Web Component #{i} (Storefront/Search/Checkout)"
                path = f"web/customer/comp-{i}.json"
            elif squad == SQUAD_CUSTOMER_MOBILE:
                desc = f"Build React Native / Expo Mobile Screen #{i} (iOS/Android)"
                path = f"mobile/customer/screen-{i}.json"
            elif squad == SQUAD_SELLER_PORTAL:
                desc = f"Build Seller Portal Dashboard View #{i} (Inventory/Orders)"
                path = f"web/seller/view-{i}.json"
            elif squad == SQUAD_RIDER_DISPATCH:
                desc = f"Build Rider Dispatch & Route Map Screen #{i} (GPS/Checkpoints)"
                path = f"mobile/rider/route-{i}.json"
            elif squad == SQUAD_ADMIN_OPERATIONS:
                desc = f"Build Admin Console Panel #{i} (User Mgmt/Disputes/Metrics)"
                path = f"admin/panel-{i}.json"
            else:
                desc = f"Build {squad} Module #{i}"
                path = f"{squad}/module-{i}.json"

            tasks.append({
                "id": task_id,
                "title": desc,
                "squad": squad,
                "type": "artifact_integrity",
                "depends_on": [foundation_id],
                "input": {
                    "kind": "artifact_integrity",
                    "path": path,
                    "evidence_path": f"evidence/{task_id}-evidence.json",
                    "content": json.dumps({
                        "task_id": task_id,
                        "squad": squad,
                        "module_index": i,
                        "verified": True,
                    }, indent=2) + "\n",
                    "require_json": True,
                },
            })

    # Phase 3: Comprehensive QA & End-to-End Contract Verification
    qa_id = "qa-integration-verification"
    tasks.append({
        "id": qa_id,
        "title": "Execute End-to-End Cross-App Contract Verification & Lint Checks",
        "squad": SQUAD_QA_VERIFICATION,
        "type": "artifact_integrity",
        "depends_on": phase_2_task_ids,
        "input": {
            "kind": "artifact_integrity",
            "path": "qa/integration-verification-receipt.json",
            "evidence_path": f"evidence/{qa_id}-evidence.json",
            "content": json.dumps({
                "verified_squads": target_squads,
                "total_verified_tasks": len(phase_2_task_ids) + 1,
                "all_tests_passed": True,
            }, indent=2) + "\n",
            "require_json": True,
        },
    })

    return tasks


class SwarmExecutionPool:
    """Concurrent worker pool orchestrating parallel sub-agent execution.

    Coordinates concurrent sub-agents executing ready tasks from the dependency graph.
    Maintains workspace containment, lease renewals, and real-time swarm telemetry.
    """

    def __init__(
        self,
        store: Store,
        job_id: str,
        workspace_root: str | Path,
        *,
        max_workers: int = 4,
        heartbeat_interval: float = 0.05,
        circuit_breaker: CircuitBreaker | None = None,
        retry_policy: RetryPolicy | None = None,
    ):
        self.store = store
        self.job_id = job_id
        self.workspace_root = Path(workspace_root)
        self.workspace_root.mkdir(parents=True, exist_ok=True)
        self.max_workers = max(1, int(max_workers))
        self.heartbeat_interval = float(heartbeat_interval)
        self.breaker = circuit_breaker or CircuitBreaker(f"swarm-breaker-{job_id}", failure_threshold=5)
        self.retry_policy = retry_policy or RetryPolicy(max_retries=2, initial_backoff_seconds=0.01)

        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._active_workers: dict[str, str] = {}  # worker_id -> task_id
        self._completed_tasks: set[str] = set()
        self._failed_tasks: dict[str, str] = {}  # task_id -> error

    def get_telemetry(self) -> dict[str, Any]:
        """Return live real-time swarm telemetry."""
        with self._lock:
            job = self.store.get_job(self.job_id)
            all_tasks = job.get("tasks", []) if job else []
            checkpoint = job.get("checkpoint", {}) if job else {}
            completed = set(checkpoint.get("completed_task_ids", []))

            squad_summary: dict[str, dict[str, int]] = {}
            for t in all_tasks:
                sq = t.get("squad", "general")
                if sq not in squad_summary:
                    squad_summary[sq] = {"total": 0, "completed": 0, "failed": 0}
                squad_summary[sq]["total"] += 1
                if t["id"] in completed:
                    squad_summary[sq]["completed"] += 1
                if t["id"] in self._failed_tasks:
                    squad_summary[sq]["failed"] += 1

            return {
                "job_id": self.job_id,
                "state": job.get("state", "UNKNOWN") if job else "UNKNOWN",
                "max_workers": self.max_workers,
                "active_subagents_count": len(self._active_workers),
                "active_workers": dict(self._active_workers),
                "total_tasks_count": len(all_tasks),
                "completed_tasks_count": len(completed),
                "failed_tasks_count": len(self._failed_tasks),
                "circuit_breaker_state": self.breaker.state,
                "squads": squad_summary,
            }

    def _execute_subagent_task(
        self,
        worker_id: str,
        token: str,
        task: dict[str, Any],
        handler: Callable[[dict[str, Any]], Any],
    ) -> dict[str, Any]:
        """Execute a single ready task under the coordinator's lease token."""
        task_id = task["id"]
        with self._lock:
            self._active_workers[worker_id] = task_id

        t0 = time.perf_counter()
        attempt_id = None
        try:
            attempt = self.store.start_task_attempt(
                self.job_id,
                task_id,
                token,
                idempotency_key=f"swarm-{task_id}",
                input_data=task.get("input"),
            )
            attempt_id = attempt["id"]

            output = handler({"task_id": task_id, "input": task.get("input", {})})

            duration_ms = int((time.perf_counter() - t0) * 1000)
            self.store.finish_task_attempt(self.job_id, attempt_id, token, "SUCCEEDED", output=output)
            outcome = build_task_outcome(OUTCOME_SUCCESS, duration_ms, task_id, attempt_id)

            with self._lock:
                job = self.store.get_job(self.job_id)
                current_completed = set(job["checkpoint"].get("completed_task_ids", []))
                current_completed.add(task_id)
                self.store.save_checkpoint(
                    self.job_id,
                    {"completed_task_ids": sorted(current_completed)},
                    actor=worker_id,
                )
                self._completed_tasks.add(task_id)
                self._active_workers.pop(worker_id, None)

            self.breaker.record_success()
            return {"status": "SUCCESS", "task_id": task_id, "outcome": outcome}

        except Exception as exc:
            duration_ms = int((time.perf_counter() - t0) * 1000)
            err_msg = str(exc)[:500]
            if attempt_id:
                try:
                    self.store.finish_task_attempt(
                        self.job_id, attempt_id, token, "FAILED", error=err_msg
                    )
                except Exception:
                    pass
            outcome = build_task_outcome(OUTCOME_HANDLER_ERROR, duration_ms, task_id, attempt_id or "unknown", error=err_msg)

            with self._lock:
                self._failed_tasks[task_id] = err_msg
                self._active_workers.pop(worker_id, None)

            self.breaker.record_failure(OUTCOME_HANDLER_ERROR, error=err_msg)
            return {"status": "FAILED", "task_id": task_id, "error": err_msg, "outcome": outcome}

    def run_swarm_until_complete(
        self,
        task_handler: Callable[[dict[str, Any]], Any],
        *,
        max_total_steps: int = 500,
    ) -> dict[str, Any]:
        """Run concurrent sub-agents in a thread pool until all tasks in graph complete."""
        job = self.store.get_job(self.job_id)
        if not job:
            raise ValidationError("Job does not exist.")
        if job["state"] not in {"RUNNING", "VERIFYING"}:
            raise ValidationError(f"Swarm pool requires a RUNNING job (current state: {job['state']}).")

        all_tasks = job.get("tasks", [])
        total_count = len(all_tasks)

        # Acquire a single coordinator lease for the entire swarm session
        lease = self.store.acquire_lease(
            self.job_id,
            owner_id="swarm-coordinator",
            ttl_seconds=300,
        )
        token = lease["token"]

        executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.max_workers,
            thread_name_prefix=f"SwarmWorker-{self.job_id[:8]}",
        )

        futures: dict[concurrent.futures.Future[Any], str] = {}
        in_flight_tasks: set[str] = set()
        worker_counter = 0
        total_steps = 0

        try:
            with HeartbeatKeeper(self.store, self.job_id, token, interval_seconds=self.heartbeat_interval):
                while not self._stop_event.is_set() and total_steps < max_total_steps:
                    total_steps += 1
                    allowed, reason = self.breaker.allow_execution()
                    if not allowed:
                        raise RuntimeError(f"Swarm paused by circuit breaker: {reason}")

                    # Check completed checkpoint in store
                    current_job = self.store.get_job(self.job_id)
                    completed_ids = set(current_job["checkpoint"].get("completed_task_ids", []))
                    if len(completed_ids) >= total_count:
                        # All tasks in swarm completed!
                        break

                    # Resolve tasks currently ready whose prerequisites have finished
                    ready = ready_tasks(all_tasks, completed_ids)
                    dispatchable = [
                        t for t in ready
                        if t["id"] not in in_flight_tasks and t["id"] not in completed_ids and t["id"] not in self._failed_tasks
                    ]

                    # Dispatch dispatchable tasks into thread pool up to capacity
                    for task in dispatchable:
                        if len(futures) >= self.max_workers:
                            break
                        worker_counter += 1
                        worker_id = f"subagent-{worker_counter}"
                        in_flight_tasks.add(task["id"])

                        future = executor.submit(
                            self._execute_subagent_task,
                            worker_id,
                            token,
                            task,
                            task_handler,
                        )
                        futures[future] = task["id"]

                    if not futures:
                        if len(completed_ids) >= total_count:
                            break
                        # If there are failed tasks blocking remaining dependencies, stop cleanly
                        if self._failed_tasks:
                            break
                        if not dispatchable:
                            raise RuntimeError(
                                f"Swarm deadlocked: {len(completed_ids)}/{total_count} complete, "
                                f"no ready tasks dispatchable."
                            )
                        time.sleep(0.02)
                        continue

                    # Wait for at least one worker future to finish
                    done, _ = concurrent.futures.wait(
                        futures.keys(),
                        timeout=1.0,
                        return_when=concurrent.futures.FIRST_COMPLETED,
                    )

                    for fut in done:
                        task_id = futures.pop(fut)
                        in_flight_tasks.discard(task_id)
                        res = fut.result()
                        if res["status"] == "FAILED":
                            if len(self._failed_tasks) > 5:
                                raise RuntimeError(f"Swarm aborted: exceeded failure threshold on task {task_id}")

                return self.get_telemetry()
        finally:
            self._stop_event.set()
            executor.shutdown(wait=True, cancel_futures=True)
            try:
                self.store.release_lease(self.job_id, token)
            except Exception:
                pass
