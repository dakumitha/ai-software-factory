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

12. **API Discovery Registry**: SQLite catalogue with source/provider URLs, pricing/licence labels, verification and human approval state, filtering, and audit history.

13. **Repository/Template Evaluator**: statically inspects an already-present local repository's bounded metadata files. It emits a JSON report and leaves adoption in REVIEW_REQUIRED. It does not clone, install, build, test, or execute repository code.

14. **Deterministic Execution Controller**: selects one ready task in stable order, resolves its explicit handler type, persists an attempt before execution, checks JSON output size, and records task completion in a durable checkpoint. Handlers are trusted in-process code, not sandboxed; missing handlers block execution. No LLM or arbitrary code execution is included. See [Execution Controller](EXECUTION_CONTROLLER.md).

## Trust boundaries

- User input and generated plans are untrusted until validated.
- Public repository code, package scripts, model output, and agent-generated commands are untrusted.
- Agent workspaces must be isolated from secrets and control-plane authority.
- The control plane validates state transitions and tool permissions.
- Registry records are metadata only; the registry does not fetch or execute a listed API, package, or sample.
- Repository evaluation is static metadata triage, not a security certification.
- The execution controller invokes only explicitly registered trusted handlers. It is not a sandbox, and it must not register model-generated code or arbitrary plugins.

## Durable state and recovery

The store persists project/job/task state, events, checkpoints, worker leases and task attempts. An attempt left STARTED after a crash is uncertain and must be reconciled before retry. Checkpoints are orchestration metadata, not independent verification. The current implementation does not guarantee exactly-once side effects or automatic crash recovery.

## Design rule

Prefer the smallest coherent system that safely coordinates existing tools. Dependencies must justify operational cost, security risk, licence, and free-tier feasibility.
