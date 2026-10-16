# Architecture and Trust Boundaries

Status: proposed architecture. Technology choices remain open until the integration audit is complete.

## Logical components

1. **Mobile-first control room**: project creation, interview, status, task board, logs, diff review, approvals, budget view, export.
2. **API/control plane**: authentication, authorisation, project state, job transitions, quotas, approval policy, audit events.
3. **Requirements service**: versioned requirements, assumptions, decisions, traceability, acceptance criteria.
4. **Planner**: decomposes work into a dependency graph; validates prerequisites and resource limits.
5. **Orchestrator**: schedules bounded tasks, handles cancellation, retries, checkpoints, and resumptions.
6. **Agent adapters**: common interface for coding agents and model providers; provider-specific capabilities and limits are explicit.
7. **Workspace executor**: isolated build/test workspace; no implicit access to control-plane credentials or production secrets.
8. **Verification service**: runs configured tests, static analysis, build, dependency/licence and security checks.
9. **Artifact and event storage**: versioned specifications, task outputs, logs, test reports, diffs, checkpoints, release manifests.
10. **Release controller**: evaluates required evidence, approval status, target configuration, rollback plan, and release state.
11. **Integration registry**: records external repositories, versions, licences, maintenance evidence, risks, and adapter status.

12. **API Discovery Registry (first slice implemented)**: a SQLite catalogue for candidate APIs, source/provider URLs, pricing and licence labels, verification state, and human approval state. It now shares the control-plane database, exposes JSON endpoints for candidate search/review/decisions, and writes a dedicated append-only registry audit stream. This is not yet a provider invocation adapter.

## Trust boundaries

- User input and generated plans are untrusted until validated.
- Public repository code, package scripts, model output, and agent-generated commands are untrusted.
- Agent workspaces are isolated from secrets and control-plane authority.
- The control plane validates every state transition and tool permission.
- Credentials are stored only in an approved secret manager or secure host configuration, never in source files or logs.
- Production deployment is a separate privileged action with explicit approval.
- External integration outputs are data, not instructions that can override system policy.
- Registry records are metadata only: the registry does not fetch or execute a listed API, package, or sample. Approval does not grant runtime access or prove provider safety.

## Durable job state

A job should record:
- stable job and project IDs;
- specification revision and requirement IDs;
- task graph revision and current task;
- source repository and commit/branch references;
- selected agent/model and configuration version;
- budget limits and measured usage when available;
- checkpoint ID and resumable state;
- logs, artifacts, test results and security findings;
- approval records and final outcome.

State changes should be explicit, validated, and idempotent. A resumed job must not blindly repeat non-idempotent external actions. Retries must be bounded and distinguish transient failures from deterministic failures.

### API Discovery Registry

The first implementation is isolated from the control-plane database. It stores candidate metadata in `data/api-registry.sqlite3`, validates HTTPS source URLs, supports filtering, and blocks approval until verification is complete, licence status is acceptable, and pricing is known. Any review change resets approval to pending. See [API Discovery Registry guide](API_DISCOVERY_REGISTRY.md) for commands, states, and limitations.

## Current checkpoint contract

The implemented control plane stores checkpoint JSON on each job and exposes `POST /jobs/{job_id}/checkpoint`. Checkpoint updates are merged into the stored checkpoint and emit a `job.checkpoint_saved` audit event when the effective state changes. Supported orchestration fields currently include `stage`, `current_task_id`, `completed_task_ids`, and `resume_count`; additional JSON fields can be retained for future adapters.

- `current_task_id`, when supplied, must identify a task in the job.
- `completed_task_ids` must contain unique IDs from that job's task graph.
- Previously completed task IDs cannot be removed by a later checkpoint.
- An identical checkpoint is a no-op and does not add duplicate audit events.
- Checkpoints persist across SQLite store re-open.

These checks protect the progress record from common accidental regressions. They do not establish exactly-once execution or prove that a task succeeded.

### Schema migrations and interrupted-job inventory

The store records applied schema versions in `schema_migrations`. Migration v1 establishes the existing project/job/event tables and is also recorded when opening a legacy database that already has those tables. Migration v2 adds indexes for state/update-time and job-event lookups. Migration v3 adds expiring worker leases. Migration v4 adds durable task-attempt records with per-job idempotency keys and terminal result states. Migrations are additive, repeatable on reopen, and refuse to start if the database declares a newer schema version than this code understands.

`GET /recovery/interrupted` inventories jobs left in `RUNNING` or `VERIFYING`, including their last checkpoint pointers. It is a read-only review queue, not an automatic resume mechanism. Jobs with an unexpired worker lease are excluded; jobs with no lease or an expired lease are surfaced for operator review. Workers acquire a lease with `POST /jobs/{job_id}/lease`, extend it through `/lease/heartbeat`, and release it through `/lease/release`. The secret token is stored only as a SHA-256 hash in SQLite and is returned only at acquisition. These leases improve ownership tracking but do not themselves execute tasks. Task attempts are recorded before execution and can be finished as `SUCCEEDED`, `FAILED`, or `UNCERTAIN`. Repeating the same idempotency key with identical task input returns the original attempt; reusing it for different input is rejected. A `STARTED` attempt left after a crash is potentially uncertain and must not be automatically retried until side effects are reconciled. These records provide at-least-once coordination primitives, not exactly-once execution.

### Database backup

`Store.backup_to(destination)` uses SQLite's online backup API to create a consistent database copy. It creates the destination directory if needed and rejects using the live database path as the destination. The method does not encrypt the copy, upload it remotely, or define retention. Operators must protect backup files and periodically test restoration by opening a copy and checking expected project/job/checkpoint/event records. Agent execution, task-attempt records, process-crash recovery, and output verification are still future work.

## Suggested job lifecycle

`DRAFT → NEEDS_CLARIFICATION → SPEC_READY → PLAN_READY → AWAITING_APPROVAL → QUEUED → RUNNING → VERIFYING → REVIEW_REQUIRED → RELEASE_READY → RELEASED`

Terminal or interrupt states include `BLOCKED`, `FAILED`, `CANCELLED`, and `PAUSED_QUOTA`. Only the controller may transition a job to a release state after validating required evidence.

## Initial implementation order

1. Repository audit and architecture decisions.
2. Data contracts and state machine.
3. Persistent project/job/task records and event log.
4. Mobile-friendly read-only status/control UI.
5. Requirements and task planning workflow.
6. One safe agent adapter in a constrained environment.
7. Verification pipeline and evidence store.
8. Approval flow, exports, and release controller.
9. Additional agents/providers and integrations only after the first vertical slice is tested.

## Design rule

Prefer the smallest coherent system that can safely coordinate existing tools. Do not add infrastructure merely because it is popular. Every dependency must justify its operational cost, security risk, licence, and free-tier feasibility.
