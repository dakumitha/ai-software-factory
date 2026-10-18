"""Release controller, deployment safety gates, and rollback management.

Enforces independent evidence verification before promoting a job to
RELEASE_READY or RELEASED. Standard state transitions prohibit direct
movement to RELEASED; this controller provides the auditable promotion path.
"""
from __future__ import annotations

import json
import sqlite3
from typing import Any

from .core import Store, ValidationError, _LOCK, utc_now
from .evidence_store import EvidenceStore


class DeliveryError(ValidationError):
    """Release or deployment violation."""


class ReleaseController:
    """Evaluate evidence gates, execute verified release, and manage rollbacks."""

    def __init__(self, store: Store, evidence_store: EvidenceStore | None = None):
        self.store = store
        self.evidence_store = evidence_store or EvidenceStore(store.path)

    def evaluate_release_readiness(self, job_id: str) -> dict[str, Any]:
        """Check all evidence and safety gates required for release."""
        job = self.store.get_job(job_id)
        if not job:
            raise DeliveryError("Job does not exist.")

        blocking_reasons: list[str] = []
        tasks = job.get("tasks", [])
        checkpoint = job.get("checkpoint", {})
        completed_ids = set(checkpoint.get("completed_task_ids", []))
        total_task_ids = {t["id"] for t in tasks}

        if job["state"] not in {"REVIEW_REQUIRED", "RELEASE_READY", "VERIFYING"}:
            blocking_reasons.append(
                f"Job is in state {job['state']!r}; must be in REVIEW_REQUIRED or RELEASE_READY."
            )

        if completed_ids != total_task_ids:
            missing = total_task_ids - completed_ids
            blocking_reasons.append(f"Unfinished tasks present in graph: {sorted(missing)}")

        evidence_summary = self.evidence_store.get_summary(job_id)
        if evidence_summary["tests_failed"] > 0:
            blocking_reasons.append(
                f"{evidence_summary['tests_failed']} automated tests failed during verification."
            )

        # Ensure budget was strictly ₹0 / $0
        if evidence_summary["total_spend_usd"] > 0.0:
            blocking_reasons.append("Zero-spend violation: non-zero financial cost detected.")

        return {
            "job_id": job_id,
            "current_state": job["state"],
            "can_release": len(blocking_reasons) == 0,
            "blocking_reasons": blocking_reasons,
            "completed_tasks": len(completed_ids),
            "total_tasks": len(total_task_ids),
            "evidence_summary": evidence_summary,
        }

    def promote_to_release_ready(self, job_id: str, actor: str = "operator") -> dict[str, Any]:
        """Promote a reviewed job to RELEASE_READY if all readiness checks pass."""
        readiness = self.evaluate_release_readiness(job_id)
        job = self.store.get_job(job_id)
        if not job:
            raise DeliveryError("Job does not exist.")

        if job["state"] == "RELEASE_READY":
            return job

        if job["state"] != "REVIEW_REQUIRED":
            # If still VERIFYING or RUNNING, attempt transition to REVIEW_REQUIRED if permitted
            if job["state"] == "VERIFYING":
                self.store.transition(job_id, "REVIEW_REQUIRED", actor=actor, reason="Verification complete")
            else:
                raise DeliveryError(
                    f"Job cannot be promoted to RELEASE_READY from state {job['state']}."
                )

        if not readiness["can_release"]:
            raise DeliveryError(
                f"Release gates failed: {'; '.join(readiness['blocking_reasons'])}"
            )

        return self.store.transition(
            job_id,
            "RELEASE_READY",
            actor=actor,
            reason="All QA verification evidence and safety gates passed.",
        )

    def execute_release(
        self,
        job_id: str,
        actor: str = "release-controller",
        notes: str = "",
    ) -> dict[str, Any]:
        """Execute final release transition with tamper-evident audit record."""
        readiness = self.evaluate_release_readiness(job_id)
        if not readiness["can_release"]:
            raise DeliveryError(
                f"Cannot release job: {'; '.join(readiness['blocking_reasons'])}"
            )

        job = self.store.get_job(job_id)
        if not job:
            raise DeliveryError("Job does not exist.")

        if job["state"] != "RELEASE_READY":
            # Attempt to promote first
            self.promote_to_release_ready(job_id, actor=actor)

        now = utc_now()
        release_receipt = {
            "released_at": now,
            "released_by": actor,
            "notes": notes,
            "evidence_summary": readiness["evidence_summary"],
            "verified_tasks_count": readiness["completed_tasks"],
        }

        # Update to RELEASED atomically and persist audit event
        with _LOCK, self.store.connect() as db:
            row = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            if not row:
                raise DeliveryError("Job does not exist.")
            checkpoint = json.loads(row["checkpoint_json"])
            checkpoint["release_receipt"] = release_receipt
            checkpoint["stage"] = "released"

            db.execute(
                "UPDATE jobs SET state='RELEASED', checkpoint_json=?, updated_at=? WHERE id=?",
                (json.dumps(checkpoint), now, job_id),
            )
            db.execute(
                "INSERT INTO events(job_id, at, actor, kind, payload_json) VALUES (?, ?, ?, ?, ?)",
                (job_id, now, actor, "job.released", json.dumps(release_receipt, sort_keys=True)),
            )

        return self.store.get_job(job_id)  # type: ignore[return-value]

    def rollback_release(
        self,
        job_id: str,
        actor: str = "operator",
        reason: str = "Rollback requested by operator",
    ) -> dict[str, Any]:
        """Safely revert a released or failed job to QUEUED for remediation."""
        job = self.store.get_job(job_id)
        if not job:
            raise DeliveryError("Job does not exist.")

        now = utc_now()
        rollback_payload = {
            "rolled_back_from": job["state"],
            "rolled_back_at": now,
            "actor": actor,
            "reason": reason,
        }

        with _LOCK, self.store.connect() as db:
            checkpoint = job["checkpoint"]
            checkpoint["last_rollback"] = rollback_payload
            checkpoint["stage"] = "queued"
            db.execute(
                "UPDATE jobs SET state='QUEUED', checkpoint_json=?, updated_at=? WHERE id=?",
                (json.dumps(checkpoint), now, job_id),
            )
            db.execute(
                "INSERT INTO events(job_id, at, actor, kind, payload_json) VALUES (?, ?, ?, ?, ?)",
                (job_id, now, actor, "job.rollback", json.dumps(rollback_payload, sort_keys=True)),
            )

        return self.store.get_job(job_id)  # type: ignore[return-value]

