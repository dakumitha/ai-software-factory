# Development Log

## 2026-10-16

### Non-executing artifact verification
- Added workspace-contained artifact inspection, a 1 MB read limit, SHA-256 comparison, optional UTF-8 JSON syntax checks, and structured evidence reports.
- Added a bounded JSON report writer and tests for success, digest mismatch, malformed JSON, missing/traversal paths, symlinks, and invalid digest input.
- Verification status: pending GitHub Actions.

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
