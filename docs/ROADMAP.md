# Accelerated Delivery Roadmap

**Deadline target: 7–14 days for a demonstrated end-to-end engine slice.** This is aggressive and conditional on free execution/model access. The target is a working, testable engine for a representative app, not universal production perfection.

## Phase 0: Foundation and control plane
- [x] Dedicated repository and product requirements.
- [x] Lightweight documentation CI.
- [x] SQLite project/job persistence, lifecycle validation, and append-only event history.
- [x] Task dependency graph validation and ready-task selection.
- [x] JSON HTTP API for projects, jobs, events, and state transitions.
- [x] Standard-library tests and Python 3.11/3.12 GitHub Actions workflow.
- [x] Durable checkpoints and ordered additive schema migrations.
- [x] Read-only interrupted-job inventory and expiring worker leases.
- [x] Durable task-attempt records, idempotency-key conflict detection, and immutable terminal outcomes.
- [x] SQLite API Discovery Registry with HTTPS URL validation, filtering, review states, approval gate, and audit history.
- [x] Registry candidate lifecycle exposed through the local control-plane API.
- [x] Explicit adapter protocol and approval-gated in-process adapter registry.
- [x] Command-line review, decision, and audit-history operations for the API registry.
- [x] Preview-first local JSON/CSV catalogue import with field allowlisting, URL validation, duplicate detection, and pending-only records.
- [ ] Safe phone-friendly control interface.
- [ ] Provider-specific adapters only after provider terms, data flow, timeouts, quotas, and tests are reviewed.

**Gate:** API discovery metadata and adapter lookup are implemented. No catalogue crawler, provider invocation, dynamic plugin loading, automatic task resume, encrypted/remote backup retention, or exactly-once side-effect handling is included.

## Phase 1: Free execution route and integration choices
- [ ] Compare Spec Kit and OpenSpec on one representative feature; select one primary.
- [ ] Identify an agent runner on a genuinely available free host/runtime.
- [ ] Verify at least one model route without paid API credit; document quotas and fallback.
- [ ] Confirm persistent artifact storage and resume behavior on the selected host.
- [ ] Record decisions and reproducible setup steps.

## Phase 2: Requirements-to-plan workflow
- [ ] Build an adaptive discovery interview storing answers, assumptions, unresolved questions, and conflicts.
- [ ] Generate versioned project specifications and acceptance criteria.
- [ ] Create dependency-aware plans with requirement traceability.
- [ ] Require explicit owner approval before agent tasks execute.
- [ ] Persist prompts/config versions, outputs, logs, checkpoints, and budget events.

## Phase 3: Agent execution and verification
- [ ] Integrate one coding-agent adapter behind a narrow interface.
- [ ] Use an isolated, disposable workspace with bounded time, output, and permissions.
- [ ] Apply changes only to a separate working branch/workspace.
- [ ] Run tests, lint/type checks, build, dependency/licence checks, and secret scanning as appropriate.
- [ ] Save patch/diff, logs, test reports, and evidence.
- [ ] Pause safely on quota exhaustion and resume from persisted state.

## Phase 4: Mobile control room and hand-off
- [ ] Responsive phone-first interface for status, logs, diffs, approvals, and export.
- [ ] API authentication and production deployment configuration.
- [ ] Exportable requirements, plans, patches, and reports.
- [ ] Owner-operated recovery documentation.

## Phase 5: Broaden coverage after the vertical slice
- [ ] Add further frameworks, languages, and agent providers based on benchmark evidence.
- [ ] Add maintenance/bug triage and optional codebase indexing.
- [ ] Add controlled deployment and rollback only after isolated verification is reliable.

## Scope and honest completion

The 7–14 day target is for the first demonstrated end-to-end slice, not a guarantee of a universal autonomous factory. Free model/host routes may change or exhaust quotas. If the free route fails, pause and report the blocker rather than silently using a paid service.

## CI budget rules

- Prefer local/static checks and one targeted workflow run over blind retries.
- Keep workflows short and read-only unless extra permissions are necessary.
- Do not run model-intensive jobs on every documentation change.
- Never disable required checks or weaken tests to turn CI green.
- Record CI usage and stop before known quota limits.
