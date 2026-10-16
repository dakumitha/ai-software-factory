# Development Log

## 2026-10-16

### Free-first agent engine integration plan
- Documented an explicit ₹0 / US$0 default budget policy, no silent paid fallback, quota-exhaustion pause behavior, and a model-free development path.
- Recorded OpenHands Software Agent SDK as an evaluation candidate, not an adopted dependency, with license, isolation, model-route and recovery gates.
- Defined the control-plane/agent trust boundary, cloud-first phone workflow constraints, and staged implementation from deterministic vertical slice to isolated worker and mobile control room.
- Linked the plan from the README; no runtime dependency or paid service was added.
- Verification status: documentation-only changes; check GitHub Actions before claiming CI success.

### Multi-product factory strategy
- Documented the long-term goal of a general-purpose factory capable of supporting publishing/newsletter, commerce marketplace, travel/accommodation marketplace and business-software product families.
- Defined reusable platform capabilities, a product-template contract, safety and production-evidence gates, and a staged delivery sequence.
- Clarified that these product families are future targets, not implemented products; the immediate priority remains a reproducible end-to-end factory slice.
- Linked the strategy from the README.
- Verification status: documentation-only change; GitHub Actions status must be checked after commit.

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
