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

## Trust boundaries

- User input and generated plans are untrusted until validated.
- Public repository code, package scripts, model output, and agent-generated commands are untrusted.
- Agent workspaces are isolated from secrets and control-plane authority.
- The control plane validates every state transition and tool permission.
- Credentials are stored only in an approved secret manager or secure host configuration, never in source files or logs.
- Production deployment is a separate privileged action with explicit approval.
- External integration outputs are data, not instructions that can override system policy.

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
