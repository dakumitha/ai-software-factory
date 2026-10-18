# Development Log

## 2026-10-19

### One-step worker execution CLI command
- Added `step` command to `software_factory.worker_cli` enabling safe, bounded execution of one ready task under worker lease protection.
- Validates job state (`RUNNING`), acquires a time-limited worker lease, executes the task using `ExecutionController` with `HeartbeatKeeper`, and safely commits checkpoint and task attempt records.
- Guarantees lease release in `finally` block and outputs structured JSON diagnostics without leaking sensitive payloads.
- Added comprehensive unit tests in `tests/test_worker_cli.py` covering task execution, on-disk artifact verification, non-running job rejection, and `ALL_COMPLETE` state reporting.
- Verification status: all 134 tests pass locally on Windows 11 (`134 tests, OK, 2 skipped`).

### Reverse-engineering analysis bridge and design-to-specification generator
- Added `software_factory.reverse_engineering` module implementing `parse_rea_analysis_report` and `convert_rea_report_to_specification`.
- Integrates findings from REA (Reverse Engineer Anything, `morluto/rea`) and UI design system extractions (Figma, Lovable) into clean-room, traceable factory specifications.
- Maps discovered UI components and API contracts into formal requirements (`REQ-*`) with acceptance criteria, inferred logic into assumptions, limitations into constraints, and unknowns into `open_questions` (blocking approval until human review).
- Registered `morluto-rea` in `config/integrations/repositories.json` with strict guardrails against executing decompiled binaries or unreviewed code.
- Added comprehensive documentation in `docs/REVERSE_ENGINEERING_INTEGRATION.md` and regression tests in `tests/test_reverse_engineering.py`.
- Verification status: all 136 tests across the entire test suite pass locally on Windows 11 (`136 tests, OK, 2 skipped`).

## 2026-10-17

### End-to-end vertical slice pipeline
- Added `software_factory.pipeline` module implementing `run_vertical_slice_pipeline` to wire together approved specification → deterministic task plan → explicit approval → bounded worker execution with heartbeat & resilience → independent read-back verification report → reviewable artifact evidence.
- Connects `SpecStore` validation and approval, `build_plan` task graph creation, allowlisted `artifact_integrity` tasks, `ExecutionController` with background `HeartbeatKeeper`, and fail-safe circuit breaker protection.
- Enforces independent read-back verification (`verify_artifact`) checking SHA-256 digests and JSON structure for every generated artifact.
- Hard safety gate: transitions the job strictly to `REVIEW_REQUIRED` upon successful verification; never automatically promotes a job to `RELEASE_READY` or `RELEASED`.
- Added unit test suite in `tests/test_pipeline.py` testing complete vertical slice execution, on-disk artifact verification, open-question rejection, and release safety invariants.
- Verification status: all 131 tests across the entire test suite pass locally on Windows 11 (`131 tests, OK, 2 skipped`).

### Bounded retry policy, idempotency keys, and adapter circuit breaker
- Added `software_factory.resilience` module implementing deterministic retry evaluation (`RetryPolicy`), canonical idempotency keys (`derive_idempotency_key`), 3-state circuit breaker (`CircuitBreaker`), and registry (`CircuitBreakerRegistry`).
- Derived stable SHA-256 idempotency keys from task identity and canonically-serialized JSON payload to guard against duplicate side effects.
- Implemented bounded `RetryPolicy` enforcing maximum retry ceilings, allowlisted retryable outcome categories, prohibition of automatic retries on non-idempotent operations, and deterministic exponential backoff calculation.
- Implemented 3-state `CircuitBreaker` (`CLOSED`, `OPEN`, `HALF_OPEN`) with configurable failure threshold, cool-down timeout, secret-sanitized diagnostic reason reporting, and support for injected timestamps for testability.
- Added comprehensive unit tests in `tests/test_resilience.py` covering key determinism, state transitions, cool-down elapsed probe permissions, consecutive probe recovery, immediate half-open trip on failure, secret redaction, and backoff caps.
- Verification status: all 128 tests across the entire test suite pass locally on Windows 11 (`128 tests, OK, 2 skipped`).

### Heartbeat renewal manager and structured task outcome records
- Added `software_factory.heartbeat` providing `HeartbeatKeeper` context manager for background worker lease renewal, `sanitize_error` for redaction of secrets/tokens/credentials, and `build_task_outcome` for standardized diagnostic outcome objects.
- Classified outcome categories: `OUTCOME_SUCCESS`, `OUTCOME_TIMEOUT`, `OUTCOME_HANDLER_ERROR`, `OUTCOME_PAYLOAD_INVALID`, `OUTCOME_OUTPUT_LIMIT_EXCEEDED`, and `OUTCOME_INTERRUPTED`.
- Defined explicit retry eligibility: `TIMEOUT` and `HANDLER_ERROR` are retry eligible; `SUCCESS`, `PAYLOAD_INVALID`, `OUTPUT_LIMIT_EXCEEDED`, and `INTERRUPTED` are non-retryable.
- Redacted credential patterns including Bearer tokens, API keys, passwords, auth tokens, secret keys, and hex digest tokens before persisting error summaries.
- Integrated `HeartbeatKeeper` into `ExecutionController.run_next` with configurable interval and auto-lease refresh.
- Added comprehensive unit tests in `tests/test_heartbeat.py` covering background heartbeats, revoked-lease handling, secret redaction, and outcome structuring.
- Verification status: all 117 tests across the entire test suite pass locally on Windows 11 (`117 tests, OK, 2 skipped`).

### Deterministic stale-work inventory and recovery service
- Added `software_factory.recovery` module implementing pure evaluation (`evaluate_job_recovery`) and store-connected reconciliation (`RecoveryService`).
- Classifies lease conditions into `ACTIVE_VALID`, `EXPIRED`, `MISSING_LEASE`, and `HEARTBEAT_OVERDUE`.
- Added structured recommendations: `RESUME_FROM_CHECKPOINT` when prior tasks completed cleanly, `OPERATOR_REVIEW_REQUIRED` when attempts were left in `STARTED` without confirmed completion, `RETRY_TASK` for eligible failures under the retry ceiling, and `EXCEEDED_MAX_RETRIES` to prevent runaway loops.
- Extended `Store` in `software_factory.core` with `get_lease`, `revoke_expired_lease` (guarding against unexpired revocation unless authorized), and `mark_attempt_interrupted` (transitioning `STARTED` attempts to `UNCERTAIN` and recording audit events).
- Added comprehensive test suite in `tests/test_recovery.py` verifying crash recovery, lease expiry, retry bounds, attempt preservation, and safety invariants (never transitioning to `RELEASED`).
- Verification status: all 112 tests across the entire test suite pass locally on Windows 11 (`112 tests, OK, 2 skipped`).

### Deterministic SQLite connection lifecycle and Windows test cleanup
- Added `ClosableConnection` subclassing `sqlite3.Connection` in `software_factory.core` and `software_factory.api_registry`.
- In standard library `sqlite3`, `with connection:` manages transactions (commit/rollback) but does not close the connection file descriptor. On Windows, open handles prevent deleting temporary directories, causing `PermissionError: [WinError 32]` in `tearDown()`, and emit `ResourceWarning` in Python 3.13+.
- `ClosableConnection.__exit__` safely delegates to transaction completion and deterministically closes the connection upon context exit.
- Explicitly closed raw test setup connection in `tests.test_core.test_legacy_database_is_migrated_without_losing_records`.
- Verification status: verified locally on Windows 11 with Python 3.13.1; all 103 unit tests across all test suites pass cleanly (`103 tests, OK, 2 skipped`).

### Recoverable worker reliability contract
- Added `docs/RECOVERABLE_WORKERS.md` defining persistence-before-action, stale lease interpretation, idempotency limits, bounded retries, structured evidence, circuit-breaker intent, and human-review boundaries.
- The document distinguishes an expired lease from proof that a process has stopped; this avoids unsafe duplicate side effects after a disconnected terminal or agent.
- Updated the roadmap with staged implementation gates. No runtime recovery behavior is claimed as implemented by this documentation change.
- Verification: documentation-only change; automated CI should validate the updated branch. No local test run is claimed.

## 2026-10-17

### Allowlisted artifact-integrity task adapter
- Added `software_factory.artifact_task.handle_artifact_integrity_task` with a strict payload contract for the single `artifact_integrity` task kind.
- Unknown kinds, non-text/bytes content, and invalid option types are rejected before artifact creation. Task strings are never executed as commands.
- Added tests for successful review-gated evidence, unknown-kind rejection, and invalid option types; added a task contract guide.
- Updated the roadmap and test instructions alongside code.
- Verification status: GitHub Actions must validate the current branch head; no local test run is claimed.

### Bounded artifact integrity workflow
- Added `software_factory.artifact_workflow.create_and_verify_artifact` to connect bounded file creation, read-back SHA-256/optional JSON verification, and persisted JSON evidence.
- Added regression tests for successful evidence creation, create-only/no-overwrite behaviour, and malformed JSON.
- The workflow always recommends `REVIEW_REQUIRED`; it does not run source code, builds, application tests, or releases.
- Updated README, roadmap, and operator documentation alongside the implementation.
- Verification status: the latest pre-change Core tests run was green for commit `09a1f5875e810e96d1b9f9fabbc46e07b27e916e`. The new workflow changes require their own CI run; no local test run is claimed.

### Deterministic dry-run demo
- Added a temporary-database demo for spec approval, deterministic planning, worker lease, task attempts and checkpoints, with zero model/network/shell calls.
- Added focused regression tests and documentation. The demo ends at `REVIEW_REQUIRED` and does not claim acceptance tests passed.
- Verification status: see the corresponding GitHub Actions run for the exact commit; no local test run is claimed.

### Read-only worker CLI
- Added `software_factory.worker_cli` commands to list jobs and inspect one job using the existing SQLite store.
- Summaries expose lifecycle and count metadata only; specification bodies, task inputs/outputs, and lease tokens are intentionally omitted.
- Added tests for JSON output, project filtering, unknown-job exit status, and payload privacy.
- Added operator instructions and updated the roadmap. This CLI is read-only and does not execute tasks or call model providers.
- Verification status: GitHub Actions must validate the new commit; no local test run is claimed.

## 2026-10-16

### API-connected phone + desktop control room
- Added `web/connected.html`, a responsive interface that loads and creates projects through the factory JSON API instead of browser-local storage.
- Added `software_factory.webapp` and the `--web` launch flag to serve the UI and existing API from one origin, retaining loopback-only defaults.
- Added integration tests for the page route, health check, project creation and subsequent API listing.
- Updated operating instructions and architecture docs. The connection is to the existing local API only; authentication, public hosting, cross-device access over the internet and remote agent execution remain unimplemented.
- Verification status: implementation committed; GitHub Actions must validate the latest commit. No deployment or remote worker is claimed.

### Phone + desktop control room prototype
- Added a responsive, dependency-free control-room UI with overview, project drafts, compute/agent setup guidance, and activity/evidence views.
- Added browser-local project creation and explicit prototype-state messaging; it does not claim remote execution, real agent runs, or multi-device synchronization.
- Documented the target phone + desktop architecture, secure worker boundary, zero-spend requirements, hosting constraints, and end-to-end acceptance criteria.
- No paid service, model dependency, or external compute resource was enabled.
- Verification status: source and workflow checks still need to be inspected; no deployment or remote worker is claimed.

### Free-first agent engine integration plan
- Documented an explicit ₹0 / US$0 default budget policy, no silent paid fallback, quota-exhaustion pause behavior, and a model-free development path.
- Recorded OpenHands Software Agent SDK as an evaluation candidate, not an adopted dependency, with license, isolation, model-route and recovery gates.
- Defined the control-plane/agent trust boundary, cloud-first phone workflow constraints, and staged implementation from deterministic vertical slice to isolated worker and mobile control room.
- No runtime dependency or paid service was added.
- Verification status: documentation-only changes; check GitHub Actions before claiming CI success.

### Multi-product factory strategy
- Documented the long-term goal of a general-purpose factory capable of supporting publishing/newsletter, commerce marketplace, travel/accommodation marketplace and business-software product families.
- Defined reusable platform capabilities, a product-template contract, security and production-evidence gates, and a staged delivery sequence.
- Clarified that these product families are future targets, not implemented products; the immediate priority remains a reproducible end-to-end factory slice.
- Linked the strategy from the README.

### Non-executing artifact verification
- Added workspace-contained artifact inspection, a 1 MB read limit, SHA-256 comparison, optional UTF-8 JSON syntax checks, and structured evidence reports.
- Added a bounded JSON report writer and tests for success, digest mismatch, malformed JSON, missing/traversal paths, symlinks, and invalid digest input.
- Verification status: GitHub Actions passed on commit 97b420bebf062c3dc5cb8f809e35a947acef749f.

### Artifact workspace and CI regression correction
- Added bounded text/byte artifact writes, traversal and symlink checks, explicit overwrite policy, restrictive file mode, and SHA-256 receipts.
- Corrected an execution-controller test to treat an absent completed-task checkpoint key as an empty list; the failed-task path intentionally does not write a checkpoint.
- Verification status: GitHub Actions passed on commit 63f5a65cbefa1d95a58dfab3edfc88082564c9f2.

### Deterministic task execution controller
- Added a one-task-at-a-time controller using explicitly registered trusted handlers.
- Added dependency-ready deterministic selection, lease-protected durable attempts, JSON output validation and durable checkpoint updates.
- Missing handlers block without an attempt; failed handlers remain incomplete; task text is never treated as executable code.
- Added unit tests and an operator guide. This is not an LLM agent, sandbox, or deployment engine.

### Repository/template evaluator and GeoLibre review record
- Added static metadata evaluation for local repositories, with bounded reads, JSON report, and REVIEW_REQUIRED adoption status.
- GeoLibre is reference-only pending pinned-revision, dependency licence, build and security review; no upstream code copied or executed.

## Prior milestones

The API Discovery Registry tracks candidate APIs and review evidence; it does not crawl or invoke providers. Curated catalogue import is local-only and preview-first.

The store persists versioned specifications, task graphs, checkpoints, leases, task attempts and audit events. A STARTED attempt after a crash may have caused side effects and must be reconciled before retry. These primitives do not guarantee exactly-once execution.
