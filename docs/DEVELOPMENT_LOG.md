# Development Log

## 2026-10-16

### Artifact workspace and CI regression correction
- Added bounded text/byte artifact writes, traversal and symlink checks, explicit overwrite policy, restrictive file mode, and SHA-256 receipts.
- Added JSON artifact output and tests for integrity metadata, traversal, symlink escape, size cap, overwrite behaviour, and JSON serialization.
- Corrected an execution-controller test to treat an absent completed-task checkpoint key as an empty list; the failed-task path intentionally does not write a checkpoint.
- Verification status: pending GitHub Actions.

### Deterministic task execution controller
- Added a one-task-at-a-time controller using explicitly registered trusted handlers.
- Added dependency-ready deterministic selection, lease-protected durable attempts, JSON output validation and durable checkpoint updates.
- Missing handlers block without an attempt; failed handlers remain incomplete; task text is never treated as executable code.
- Added unit tests and an operator guide. This is not an LLM agent, sandbox, or deployment engine.
- Verification status: see preceding CI run for the initially failing assertion.

### Repository/template evaluator and GeoLibre review record
- Added static metadata evaluation for local repositories, with bounded reads, JSON report, and REVIEW_REQUIRED adoption status.
- GeoLibre is reference-only pending pinned-revision, dependency licence, build and security review; no upstream code copied or executed.
- Verification status: see CI for preceding commit.

## Prior milestones

The API Discovery Registry tracks candidate APIs and review evidence; it does not crawl or invoke providers. Curated catalogue import is local-only and preview-first.

The store persists versioned specifications, task graphs, checkpoints, leases, task attempts and audit events. A STARTED attempt after a crash may have caused side effects and must be reconciled before retry. These primitives do not guarantee exactly-once execution.
