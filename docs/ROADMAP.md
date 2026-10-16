# Accelerated Delivery Roadmap

**Deadline target: 7–14 days for a demonstrated end-to-end engine slice.** The target is aggressive and conditional on free execution/model access being available. The result should be a working, testable engine that creates and verifies a representative application, not a claim that every software category is production-perfect.

## Phase 0: Foundation and control plane
- [x] Create dedicated repository and product requirements.
- [x] Add lightweight documentation CI.
- [x] Implement SQLite project/job persistence.
- [x] Implement explicit job lifecycle validation and append-only event history.
- [x] Validate task dependency graphs and provide ready-task selection.
- [x] Add JSON HTTP endpoints for projects, jobs, events, and state transitions.
- [x] Add standard-library unit tests and a Python 3.11/3.12 GitHub Actions workflow.
- [x] Verify the core-test workflow is green in GitHub Actions for the current feature-branch head (run 38840047085).
- [x] Add API integration tests for the current control-plane and specification endpoints.
- [ ] Build a safe phone-friendly control interface.

- [x] Add durable checkpoint update API with validation and audit events.
- [x] Test checkpoint persistence across store reopen, idempotent repeated writes, unknown task rejection, and completed-task regression rejection.

**Gate:** current control-plane, specification, and checkpoint tests pass in GitHub Actions. Full interrupted-job resume, task-attempt recovery, backup/restore, and exactly-once external side-effect handling remain unimplemented.

## Phase 1: Free execution route and integration choices
- [ ] Compare Spec Kit and OpenSpec on one representative feature; select one primary.
- [ ] Identify an agent runner that can run on a genuinely available free host or free-tier runtime.
- [ ] Verify at least one model route without paid API credit; document quotas, acceptable use, and fallback.
- [ ] Confirm persistent artifact storage and job resume behaviour on the selected host.
- [ ] Record decisions, limitations, and reproducible setup steps.

**Gate:** one real execution path is proven without assuming unlimited free compute.

## Phase 2: Requirements-to-plan workflow
- [ ] Build an adaptive discovery interview that stores answers, assumptions, unresolved questions, and conflicts.
- [ ] Generate versioned project specifications and acceptance criteria.
- [ ] Create dependency-aware plans with requirement traceability.
- [ ] Require explicit owner approval before executing agent tasks.
- [ ] Persist prompts/config versions, outputs, logs, checkpoints, and budget events.

**Gate:** a plain-language idea becomes a reviewable, saved specification and executable plan.

## Phase 3: Agent execution and verification
- [ ] Integrate one coding-agent adapter, behind a narrow interface.
- [ ] Use an isolated, disposable workspace with bounded time, output, and permissions.
- [ ] Apply changes only to a separate working branch/workspace.
- [ ] Run tests, lint/type checks, build, dependency/license checks, and secret scanning as appropriate.
- [ ] Save patch/diff, logs, test reports, and evidence.
- [ ] Pause safely on quota exhaustion and resume from persisted state.

**Gate:** one sample app is generated/modified and verification evidence is recorded; failures block completion.

## Phase 4: Mobile control room and hand-off
- [ ] Provide a responsive phone-first interface for projects, job status, logs, diffs, approval, and export.
- [ ] Add safe API authentication and production deployment configuration.
- [ ] Add exportable requirements, plans, patches, and reports.
- [ ] Document limitations and owner-operated recovery.

**Gate:** owner can supervise the full demonstrated workflow from a phone without needing a local development computer.

## Phase 5: Broaden coverage after the vertical slice
- [ ] Add further frameworks, languages, and agent providers based on benchmark evidence.
- [ ] Add maintenance/bug triage and optional codebase indexing.
- [ ] Add controlled deployment and rollback only after isolated verification is reliable.
- [ ] Add more sophisticated memory/search only if baseline persistence is insufficient.

## Scope and honest completion

The 7–14 day target applies to the first demonstrated end-to-end engine slice. It does not guarantee a universal, production-grade autonomous software factory across every stack. The external model/host route is the principal risk because free tiers can change or exhaust quotas. If the free route fails, pause and report the blocker rather than silently using a paid service.

## CI budget rules

- Prefer local/static checks and one targeted workflow run over blind retries.
- Keep workflows short, pinned, and read-only unless a job truly requires more permission.
- Do not run model-intensive jobs on every documentation change.
- Never disable required checks or weaken tests to turn CI green.
- Record CI usage and stop before known quota limits.
