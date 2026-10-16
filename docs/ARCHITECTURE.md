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

12. **API Discovery Registry**: SQLite catalogue with source/provider URLs, pricing/licence labels, verification and human approval state, filtering, and audit history. The provider_adapters module defines an explicit in-process adapter protocol and approval-gated registry. It does not load dynamic plugins or call external APIs.

## Trust boundaries

- User input and generated plans are untrusted until validated.
- Public repository code, package scripts, model output, and agent-generated commands are untrusted.
- Agent workspaces are isolated from secrets and control-plane authority.
- The control plane validates every state transition and tool permission.
- Credentials belong only in an approved secret manager or secure host configuration, never source files or logs.
- Production deployment is a separate privileged action with explicit approval.
- External integration outputs are data, not instructions that can override system policy.
- Registry records are metadata only; the registry does not fetch or execute a listed API, package, or sample.
- Adapter objects are trusted code supplied explicitly by the application owner. The registry checks candidate approval and operation names but is not a sandbox.

## API Discovery Registry

The registry shares the configured SQLite database with the control plane, validates HTTPS source URLs, supports filtering, and blocks approval until verification is complete, licence status is acceptable, and pricing is known. Any review change resets approval to pending. Adapter registration and lookup are gates only, not live connectors. See [API Discovery Registry guide](API_DISCOVERY_REGISTRY.md).

## Durable job state

A job should record stable job/project IDs, specification revision, requirement IDs, task graph revision, current task, source repository/commit, selected agent/model, configuration version, budget limits, checkpoint ID, logs, artifacts, test results, security findings, approvals, and final outcome.

State changes should be explicit, validated, and idempotent. A resumed job must not blindly repeat non-idempotent external actions. Retries must be bounded and distinguish transient from deterministic failures.

## Current checkpoint contract

The control plane stores checkpoint JSON on each job and exposes POST /jobs/{job_id}/checkpoint. Updates are merged and audited when effective state changes. Supported fields include stage, current_task_id, completed_task_ids, and resume_count. Current task must exist in the graph; completed IDs must be unique and valid; prior completed IDs cannot be removed. Identical updates are no-ops. These checks do not establish exactly-once execution or prove task success.

## Schema migrations and interrupted-job inventory

The store tracks schema migrations. Migration v1 establishes project/job/event tables; v2 adds indexes; v3 adds expiring worker leases; v4 adds durable task attempts with idempotency keys and terminal result states. Migrations are additive and reject a newer unsupported schema. GET /recovery/interrupted inventories RUNNING/VERIFYING jobs without automatically resuming them. Live leases are excluded; missing/expired leases require operator review. Task attempts left STARTED after a crash are uncertain and must not be retried until side effects are reconciled. These are coordination primitives, not exactly-once guarantees.

## Database backup

Store.backup_to(destination) uses SQLite's online backup API. It does not encrypt copies, upload remotely, or define retention. Protect backup files and periodically test restoration. Agent execution, complete crash recovery, and output verification remain future work.

## Suggested lifecycle

DRAFT → NEEDS_CLARIFICATION → SPEC_READY → PLAN_READY → AWAITING_APPROVAL → QUEUED → RUNNING → VERIFYING → REVIEW_REQUIRED → RELEASE_READY → RELEASED

Only the controller may transition a job to release after validating required evidence.

## Initial implementation order

1. Repository audit and architecture decisions.
2. Data contracts and state machine.
3. Persistent project/job/task records and event log.
4. Mobile-friendly status/control UI.
5. Requirements and task planning workflow.
6. One safe agent adapter in a constrained environment.
7. Verification pipeline and evidence store.
8. Approval flow, exports, and release controller.
9. Additional integrations after the first vertical slice is tested.

## Design rule

Prefer the smallest coherent system that safely coordinates existing tools. Every dependency must justify operational cost, security risk, licence, and free-tier feasibility.


## API registry operator workflow

The registry CLI supports candidate creation, search, review, approval/rejection, and audit-history inspection against a chosen SQLite database. Review and decision commands use the same policy gates as the HTTP API. The CLI records operator-supplied evidence; it does not independently verify provider claims or retrieve API-mega-list entries.
