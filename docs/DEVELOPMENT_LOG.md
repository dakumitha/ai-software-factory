# Development Log

## 2026-10-17

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
