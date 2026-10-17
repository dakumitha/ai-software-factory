"""Deterministic recovery evaluator and stale-worker reconciliation.

This module inspects persisted jobs, leases, task attempts, and checkpoints to
provide structured recovery recommendations. It never executes arbitrary shell
commands, runs unverified model code, or bypasses operator review.

A stale or expired lease is treated as 'suspected stalled', not proof that a
process has cleanly halted. Side effects from interrupted attempts are treated
as uncertain until reconciled.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .core import Store, ValidationError, ready_tasks, utc_now

# Lease condition classifications
LEASE_ACTIVE_VALID = "ACTIVE_VALID"
LEASE_EXPIRED = "EXPIRED"
LEASE_MISSING = "MISSING_LEASE"
LEASE_HEARTBEAT_OVERDUE = "HEARTBEAT_OVERDUE"

# Structured recovery recommendations
REC_NO_RECOVERY_NEEDED = "NO_RECOVERY_NEEDED"
REC_RESUME_FROM_CHECKPOINT = "RESUME_FROM_CHECKPOINT"
REC_OPERATOR_REVIEW_REQUIRED = "OPERATOR_REVIEW_REQUIRED"
REC_RETRY_TASK = "RETRY_TASK"
REC_EXCEEDED_MAX_RETRIES = "EXCEEDED_MAX_RETRIES"
REC_ALL_TASKS_COMPLETE = "ALL_TASKS_COMPLETE"


def parse_iso(ts: str) -> datetime:
    """Parse an ISO 8601 UTC timestamp string into a timezone-aware datetime."""
    dt = datetime.fromisoformat(ts)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def classify_lease_state(
    lease: dict[str, Any] | None,
    now: str | None = None,
    heartbeat_grace_seconds: int = 120,
) -> str:
    """Classify the condition of a worker lease based on expiry and heartbeat timestamps.

    - MISSING_LEASE: No lease record exists for the job.
    - EXPIRED: The lease expiry timestamp has passed.
    - HEARTBEAT_OVERDUE: The lease is unexpired, but the worker has missed its expected
      heartbeat window by more than heartbeat_grace_seconds.
    - ACTIVE_VALID: The lease is unexpired and heartbeat is fresh.
    """
    if not lease:
        return LEASE_MISSING

    current_ts = now or utc_now()
    expires_at = lease.get("expires_at", "")
    if not expires_at or expires_at <= current_ts:
        return LEASE_EXPIRED

    heartbeat_at = lease.get("heartbeat_at") or lease.get("acquired_at", "")
    if heartbeat_at:
        hb_dt = parse_iso(heartbeat_at)
        now_dt = parse_iso(current_ts)
        elapsed_seconds = (now_dt - hb_dt).total_seconds()
        if elapsed_seconds > heartbeat_grace_seconds:
            return LEASE_HEARTBEAT_OVERDUE

    return LEASE_ACTIVE_VALID


def evaluate_job_recovery(
    job: dict[str, Any],
    lease: dict[str, Any] | None,
    attempts: list[dict[str, Any]],
    checkpoint: dict[str, Any] | None,
    now: str | None = None,
    heartbeat_grace_seconds: int = 120,
    max_retries: int = 3,
) -> dict[str, Any]:
    """Pure, deterministic evaluation of an interrupted or active job's recovery state.

    This function observes database snapshots without performing mutations or executing code.
    It returns a structured diagnostic report with actionable, policy-compliant recommendations.
    """
    current_ts = now or utc_now()
    job_id = job["id"]
    project_id = job.get("project_id", "")
    state = job["state"]
    tasks = job.get("tasks", [])
    all_task_ids = {t["id"] for t in tasks}

    cp = checkpoint or job.get("checkpoint", {})
    completed_task_ids = sorted(set(cp.get("completed_task_ids", [])))

    lease_state = classify_lease_state(lease, now=current_ts, heartbeat_grace_seconds=heartbeat_grace_seconds)
    lease_owner = lease.get("owner_id") if lease else None
    lease_expires = lease.get("expires_at") if lease else None
    last_heartbeat = lease.get("heartbeat_at") if lease else None

    # Find the latest attempt and any active in-flight attempt
    in_flight_attempt = None
    started_attempts = [a for a in attempts if a.get("status") == "STARTED"]
    if started_attempts:
        in_flight_attempt = started_attempts[-1]

    # Calculate attempt counts per task to enforce bounded retry policy
    latest_task_id = None
    task_attempt_counts: dict[str, int] = {}
    for a in attempts:
        tid = a.get("task_id", "")
        task_attempt_counts[tid] = task_attempt_counts.get(tid, 0) + 1
        latest_task_id = tid

    latest_attempt = attempts[-1] if attempts else None
    latest_attempt_status = latest_attempt.get("status") if latest_attempt else None
    retry_count = task_attempt_counts.get(latest_task_id, 0) if latest_task_id else 0

    # Decision tree based on safety invariants
    # 1. Non-active jobs do not require recovery
    if state not in {"RUNNING", "VERIFYING"}:
        return {
            "job_id": job_id,
            "project_id": project_id,
            "job_state": state,
            "lease_state": lease_state,
            "lease_owner": lease_owner,
            "lease_expires_at": lease_expires,
            "last_heartbeat_at": last_heartbeat,
            "recommendation": REC_NO_RECOVERY_NEEDED,
            "safe_to_reacquire_lease": False,
            "current_task_id": cp.get("current_task_id"),
            "completed_task_ids": completed_task_ids,
            "in_flight_attempt": None,
            "retry_count": retry_count,
            "max_retries": max_retries,
            "reason": f"Job is in '{state}' state; recovery only applies to active execution states.",
        }

    # 2. Healthy active worker with unexpired lease and recent heartbeat
    if lease_state == LEASE_ACTIVE_VALID:
        return {
            "job_id": job_id,
            "project_id": project_id,
            "job_state": state,
            "lease_state": lease_state,
            "lease_owner": lease_owner,
            "lease_expires_at": lease_expires,
            "last_heartbeat_at": last_heartbeat,
            "recommendation": REC_NO_RECOVERY_NEEDED,
            "safe_to_reacquire_lease": False,
            "current_task_id": cp.get("current_task_id"),
            "completed_task_ids": completed_task_ids,
            "in_flight_attempt": in_flight_attempt,
            "retry_count": retry_count,
            "max_retries": max_retries,
            "reason": f"Worker '{lease_owner}' holds an active, healthy lease.",
        }

    # 3. All tasks in the plan are already finished according to durable checkpoint
    if all_task_ids and set(completed_task_ids) == all_task_ids:
        return {
            "job_id": job_id,
            "project_id": project_id,
            "job_state": state,
            "lease_state": lease_state,
            "lease_owner": lease_owner,
            "lease_expires_at": lease_expires,
            "last_heartbeat_at": last_heartbeat,
            "recommendation": REC_ALL_TASKS_COMPLETE,
            "safe_to_reacquire_lease": lease_state in {LEASE_EXPIRED, LEASE_MISSING},
            "current_task_id": None,
            "completed_task_ids": completed_task_ids,
            "in_flight_attempt": None,
            "retry_count": retry_count,
            "max_retries": max_retries,
            "reason": "All tasks are complete in checkpoint; ready for verification or review.",
        }

    # 4. If an attempt was left in STARTED when the lease expired, side effects are uncertain
    if in_flight_attempt is not None:
        return {
            "job_id": job_id,
            "project_id": project_id,
            "job_state": state,
            "lease_state": lease_state,
            "lease_owner": lease_owner,
            "lease_expires_at": lease_expires,
            "last_heartbeat_at": last_heartbeat,
            "recommendation": REC_OPERATOR_REVIEW_REQUIRED,
            "safe_to_reacquire_lease": False,
            "current_task_id": in_flight_attempt.get("task_id"),
            "completed_task_ids": completed_task_ids,
            "in_flight_attempt": in_flight_attempt,
            "retry_count": retry_count,
            "max_retries": max_retries,
            "reason": (
                f"Task attempt '{in_flight_attempt.get('id')}' for task '{in_flight_attempt.get('task_id')}' "
                f"was left in STARTED state while lease is '{lease_state}'. Side effects cannot be assumed "
                f"absent; manual operator review is required to prevent duplicate work."
            ),
        }

    # 5. Heartbeat overdue while lease timestamp has not yet expired
    if lease_state == LEASE_HEARTBEAT_OVERDUE:
        return {
            "job_id": job_id,
            "project_id": project_id,
            "job_state": state,
            "lease_state": lease_state,
            "lease_owner": lease_owner,
            "lease_expires_at": lease_expires,
            "last_heartbeat_at": last_heartbeat,
            "recommendation": REC_OPERATOR_REVIEW_REQUIRED,
            "safe_to_reacquire_lease": False,
            "current_task_id": cp.get("current_task_id"),
            "completed_task_ids": completed_task_ids,
            "in_flight_attempt": None,
            "retry_count": retry_count,
            "max_retries": max_retries,
            "reason": (
                f"Worker '{lease_owner}' lease has not expired, but heartbeats are overdue by more than "
                f"{heartbeat_grace_seconds}s. The worker may be stalled or disconnected."
            ),
        }

    # 6. If the latest attempt failed, check retry policy limits
    if latest_attempt_status == "FAILED":
        if retry_count >= max_retries:
            return {
                "job_id": job_id,
                "project_id": project_id,
                "job_state": state,
                "lease_state": lease_state,
                "lease_owner": lease_owner,
                "lease_expires_at": lease_expires,
                "last_heartbeat_at": last_heartbeat,
                "recommendation": REC_EXCEEDED_MAX_RETRIES,
                "safe_to_reacquire_lease": False,
                "current_task_id": latest_task_id,
                "completed_task_ids": completed_task_ids,
                "in_flight_attempt": None,
                "retry_count": retry_count,
                "max_retries": max_retries,
                "reason": (
                    f"Task '{latest_task_id}' has failed {retry_count} times, reaching the limit "
                    f"of {max_retries}. Automated retries are paused to prevent runaway loops."
                ),
            }
        return {
            "job_id": job_id,
            "project_id": project_id,
            "job_state": state,
            "lease_state": lease_state,
            "lease_owner": lease_owner,
            "lease_expires_at": lease_expires,
            "last_heartbeat_at": last_heartbeat,
            "recommendation": REC_RETRY_TASK,
            "safe_to_reacquire_lease": lease_state in {LEASE_EXPIRED, LEASE_MISSING},
            "current_task_id": latest_task_id,
            "completed_task_ids": completed_task_ids,
            "in_flight_attempt": None,
            "retry_count": retry_count,
            "max_retries": max_retries,
            "reason": (
                f"Task '{latest_task_id}' failed (attempt {retry_count} of {max_retries}). "
                f"Eligible for bounded retry after lease acquisition."
            ),
        }

    # 7. Checkpoint is clean and ready tasks exist: safe to acquire new lease and resume
    ready = ready_tasks(tasks, set(completed_task_ids))
    next_task_id = sorted(ready, key=lambda t: t["id"])[0]["id"] if ready else None
    return {
        "job_id": job_id,
        "project_id": project_id,
        "job_state": state,
        "lease_state": lease_state,
        "lease_owner": lease_owner,
        "lease_expires_at": lease_expires,
        "last_heartbeat_at": last_heartbeat,
        "recommendation": REC_RESUME_FROM_CHECKPOINT,
        "safe_to_reacquire_lease": lease_state in {LEASE_EXPIRED, LEASE_MISSING},
        "current_task_id": next_task_id,
        "completed_task_ids": completed_task_ids,
        "in_flight_attempt": None,
        "retry_count": retry_count,
        "max_retries": max_retries,
        "reason": (
            f"Prior work is safely recorded in checkpoint ({len(completed_task_ids)} completed). "
            f"No uncertain attempts exist. Safe to acquire lease and execute next ready task ('{next_task_id}')."
        ),
    }


class RecoveryService:
    """Deterministic recovery service managing stale-work inventory and reconciliation."""

    def __init__(self, store: Store):
        self.store = store

    def evaluate_job(
        self,
        job_id: str,
        now: str | None = None,
        heartbeat_grace_seconds: int = 120,
        max_retries: int = 3,
    ) -> dict[str, Any]:
        """Evaluate recovery status for a single job."""
        job = self.store.get_job(job_id)
        if not job:
            raise ValidationError(f"Job '{job_id}' does not exist.")
        lease = self.store.get_lease(job_id)
        attempts = self.store.list_task_attempts(job_id)
        return evaluate_job_recovery(
            job=job,
            lease=lease,
            attempts=attempts,
            checkpoint=job.get("checkpoint"),
            now=now,
            heartbeat_grace_seconds=heartbeat_grace_seconds,
            max_retries=max_retries,
        )

    def inventory_stale_work(
        self,
        now: str | None = None,
        heartbeat_grace_seconds: int = 120,
        max_retries: int = 3,
    ) -> list[dict[str, Any]]:
        """Scan all active jobs and return structured evaluation reports for those needing attention."""
        stale_reports = []
        with self.store.connect() as db:
            rows = db.execute(
                "SELECT id FROM jobs WHERE state IN ('RUNNING', 'VERIFYING') ORDER BY updated_at ASC"
            ).fetchall()

        for row in rows:
            evaluation = self.evaluate_job(
                row["id"],
                now=now,
                heartbeat_grace_seconds=heartbeat_grace_seconds,
                max_retries=max_retries,
            )
            if evaluation["recommendation"] != REC_NO_RECOVERY_NEEDED:
                stale_reports.append(evaluation)
        return stale_reports

    def reconcile_job(
        self,
        job_id: str,
        actor: str = "recovery_service",
        now: str | None = None,
        heartbeat_grace_seconds: int = 120,
        max_retries: int = 3,
    ) -> dict[str, Any]:
        """Apply safe deterministic reconciliation to an interrupted job under policy rules.

        - Revokes expired leases, preserving previous lease history in audit logs.
        - Marks in-flight STARTED attempts as UNCERTAIN so they are preserved and never silently wiped.
        - Emits a job.recovery_reconciled audit event.
        - Never automatically marks unverified code as released or accepted.
        """
        evaluation = self.evaluate_job(
            job_id,
            now=now,
            heartbeat_grace_seconds=heartbeat_grace_seconds,
            max_retries=max_retries,
        )

        reconciled_actions = []

        # 1. If an attempt was left in STARTED, mark it as UNCERTAIN to capture crash evidence
        in_flight = evaluation.get("in_flight_attempt")
        if in_flight and in_flight.get("status") == "STARTED":
            self.store.mark_attempt_interrupted(
                job_id=job_id,
                attempt_id=in_flight["id"],
                actor=actor,
                reason="Attempt interrupted; left in STARTED state when worker lease lapsed.",
                now=now,
            )
            reconciled_actions.append(f"marked_attempt_{in_flight['id']}_uncertain")

        # 2. If lease is expired, revoke it to clear the lock for future recovery
        if evaluation["lease_state"] == LEASE_EXPIRED:
            revoked = self.store.revoke_expired_lease(
                job_id=job_id,
                actor=actor,
                reason="Lease expired; revoked by recovery reconciliation.",
                now=now,
            )
            if revoked:
                reconciled_actions.append("expired_lease_revoked")

        # Record audit event of reconciliation
        with self.store.connect() as db:
            self.store._event(
                db,
                job_id,
                actor,
                "job.recovery_reconciled",
                {
                    "initial_recommendation": evaluation["recommendation"],
                    "actions_applied": reconciled_actions,
                    "lease_state": evaluation["lease_state"],
                },
            )

        # Return refreshed evaluation alongside record of actions taken
        refreshed_evaluation = self.evaluate_job(
            job_id,
            now=now,
            heartbeat_grace_seconds=heartbeat_grace_seconds,
            max_retries=max_retries,
        )
        return {
            "job_id": job_id,
            "actions_applied": reconciled_actions,
            "evaluation_before": evaluation,
            "evaluation_after": refreshed_evaluation,
        }

