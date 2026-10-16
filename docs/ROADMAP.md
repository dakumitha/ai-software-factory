# Accelerated Delivery Roadmap

The fastest responsible route is to audit first, reuse proven components, and deliver in small verified increments. Calendar estimates remain provisional until the available hosting, model access, and candidate repositories are confirmed.

## Phase 0: Establish the foundation
- [x] Create a dedicated repository.
- [x] Record product vision, requirements, architecture boundaries, integration audit rules, and roadmap.
- [ ] Confirm repository access and baseline branch/commit.
- [ ] Add contribution, security reporting, and decision-record conventions.
- [ ] Establish lightweight CI that does not call paid AI services.

**Gate:** baseline documentation is internally consistent and repository changes are visible.

## Phase 1: Candidate audit and hosting feasibility
- [ ] Inspect the candidate repositories and exact licences.
- [ ] Compare Spec Kit and OpenSpec; select one primary specification workflow unless evidence supports both.
- [ ] Evaluate OpenHands or a lighter alternative against available free execution.
- [ ] Verify available free model endpoints and actual usage restrictions.
- [ ] Compare hosting/database options for sleeping, quota, storage, and persistence limits.
- [ ] Publish a decision record with evidence and fallback options.

**Gate:** one credible, affordable route exists for a working vertical slice. No service is described as free without checking its current terms.

## Phase 2: Control-plane core
- [ ] Define typed schemas for projects, requirements, tasks, jobs, checkpoints, approvals, artifacts, budgets, and audit events.
- [ ] Implement validated job state transitions.
- [ ] Add durable persistence and restart recovery.
- [ ] Add bounded retries, cancellation, and quota pause/resume.
- [ ] Add unit and state-transition tests.

**Gate:** jobs resume from persisted state without duplicating unsafe side effects.

## Phase 3: First complete vertical slice
- [ ] Create a project from a plain-language idea.
- [ ] Ask clarifying questions and save a versioned specification.
- [ ] Generate a dependency-aware task plan.
- [ ] Require approval before agent execution.
- [ ] Run one small coding task in an isolated workspace.
- [ ] Store patch, logs, test output, and usage evidence.
- [ ] Show results in the phone-friendly interface.

**Gate:** demonstrate idea-to-verified-change end-to-end with a sample repository and no paid service requirement for the tested path, or document exactly where a free-tier limit blocks it.

## Phase 4: Verification and governance
- [ ] Test/lint/typecheck/build adapters.
- [ ] Dependency, licence, secret and security scanning.
- [ ] Diff review and approval records.
- [ ] Artifact export and audit history.
- [ ] Release readiness checks and rollback instructions.

**Gate:** failed checks block completion and release claims.

## Phase 5: Scale integrations
- [ ] Add additional agent/model adapters only after measuring quality and cost.
- [ ] Add memory/search if baseline relational/event storage is insufficient.
- [ ] Add repository graph/context tools where benchmarks show value.
- [ ] Add issue triage, maintenance, and deployment adapters.
- [ ] Add multi-project isolation and operational dashboards.

**Gate:** each integration has a measurable benefit, tests, and a removal/fallback path.

## Scope and estimates

A 6–12 week integration programme can be used as a planning target for a substantial integrated release, but is not a guarantee of complete production-grade coverage. The schedule depends on external quotas, available execution, integration compatibility, and the breadth of supported software types. The definition of complete remains evidence-based, not deadline-based.

## CI budget rules

- Prefer local/static checks and one targeted workflow run over blind retries.
- Cache dependencies where safe.
- Do not run model-intensive jobs on every documentation change.
- Never disable required checks or weaken tests to turn CI green.
- Record CI usage and stop before known quota limits.
