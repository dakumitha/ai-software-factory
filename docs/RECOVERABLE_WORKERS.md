# Recoverable Worker Reliability

## Purpose

This document defines the next reliability increment for the AI Software Factory. The goal is to ensure a stalled or disconnected worker cannot silently hold a job forever, and that recovery does not blindly duplicate completed work.

This is an implementation contract, not a claim that every mechanism is already implemented.

## Current baseline

The control plane persists jobs in SQLite, validates lifecycle transitions, records events, stores checkpoints and task attempts, and tracks worker leases. The deterministic execution controller runs only explicitly registered Python handlers. The current artifact-integrity workflow is bounded and always stops for human review.

The controller is not an isolated sandbox and must not be exposed as a public execution service.

## Reliability contract

1. **Persist before acting.** Record the attempt and its input fingerprint before invoking a handler.
2. **Bound waiting.** Every future worker adapter must define a task timeout and a heartbeat/lease policy. A missing heartbeat means "suspected stalled", not proof that a process has stopped.
3. **Separate worker health from job truth.** The database is the source of truth for job/task state. A terminal or IDE status indicator is only an observation.
4. **Capture structured evidence.** Record task ID, attempt ID, worker ID, start/end timestamps, duration, outcome category, and a bounded error summary. Do not log secrets, access tokens, or full sensitive payloads.
5. **Retry only under policy.** A retry must be explicit, bounded, and allowed for the outcome category. Do not automatically retry non-idempotent side effects.
6. **Use idempotency keys.** Use a stable key derived from task identity and canonical input fingerprint when a handler supports idempotency. This is protection against duplicate work, not a guarantee of exactly-once execution.
7. **Circuit-break failing adapters.** Repeated timeouts or provider failures should pause that adapter and surface a reviewable reason instead of hammering the provider or spending quota.
8. **Human review remains authoritative.** Recovery must never release, deploy, merge, or mark unverified application code as accepted.

## Stale lease recovery design

A recovery operation should:

- inspect the persisted lease expiry and the last heartbeat, where available;
- distinguish an expired lease from a confirmed dead process;
- append an audit event describing the decision;
- mark the attempt as interrupted or eligible for review, rather than claiming it never ran;
- allow a new lease only after the prior lease is expired or explicitly revoked under policy;
- resume from the latest validated checkpoint;
- verify prior outputs before skipping a task;
- preserve all previous attempts and evidence.

A lease timeout is not sufficient to safely repeat an external side effect. External workers must use idempotent operations or require manual review before retry.

## Initial implementation order

1. **[Completed]** Add tests around lease expiry, stale-worker rejection, and audit history using a temporary SQLite database (`tests/test_recovery.py`).
2. **[Completed]** Add a deterministic recovery service that inventories stale work and emits recommendations without running commands (`software_factory.recovery`).
3. **[Completed]** Add bounded heartbeat updates and a structured task outcome record (`software_factory.heartbeat`).
4. Add retry policy and an adapter circuit breaker after outcome categories are stable.
5. Add a real isolated build/test worker only after sandbox boundaries, resource limits, logs, cancellation, and cleanup are independently reviewed.

## Required tests

- A worker with a valid lease can update its heartbeat.
- An expired or replaced lease token cannot mutate job state.
- Recovery preserves the previous attempt and checkpoint history.
- A stale lease is not treated as proof that a process has terminated.
- Re-running a completed deterministic task does not duplicate its committed result.
- Retry limits and circuit-breaker thresholds are deterministic and testable.
- No recovery path can transition a job directly to `RELEASED`.

## Resource and safety policy

The default budget remains USD 0. Paid services, external execution, new runtime dependencies, and deployment remain disabled unless separately approved. Recovery logic must not execute arbitrary shell commands or generated source code.
