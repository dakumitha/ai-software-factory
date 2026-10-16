# Development Log

This log records meaningful milestones and verified evidence. It does not replace Git history, CI results, or release records.

## 2026-10-16

### Repository/template evaluator and GeoLibre review record
- Added a standard-library evaluator for metadata in an already-present local repository.
- Added bounded reads, manifest/lockfile/licence/CI/test/security-policy detection, lifecycle-script warnings, JSON report output, and a permanent REVIEW_REQUIRED adoption state.
- Added tests for metadata detection, malformed manifests, missing directories, oversized files, and non-execution warnings.
- Added a GeoLibre preliminary record as REFERENCE_ONLY, REVIEW_REQUIRED; no upstream code was copied or executed.
- Verification status: pending GitHub Actions.

### API Discovery Registry: safe local catalogue import
- Added preview-first JSON/CSV import for operator-supplied local catalogue subsets, without crawling or copying the full API-mega-list catalogue.
- Added field allowlisting, a 5,000-record cap, HTTPS URL validation, duplicate detection, and explicit --apply opt-in.
- Imported records remain PENDING and UNVERIFIED; no provider is called and no content is executed.
- Added tests for preview, apply status, invalid URLs, duplicate handling, JSON/CSV input, unknown fields, and file-size limits.
- Verification status: pending GitHub Actions.

### API Discovery Registry: operator CLI lifecycle
- Added CLI commands for reviewing candidate evidence, approving/rejecting candidates, and inspecting audit history.
- Added operator actor labels and constrained status choices; approval policy remains enforced by the registry.
- Documented repeatable commands and clarified that statuses are operator assertions, not automated verification.
- Verification status: pending GitHub Actions.

### API Discovery Registry: approval-gated adapter interface
- Added ProviderAdapter protocol and in-memory AdapterRegistry for explicitly constructed trusted adapter objects.
- Registration requires an approved catalogue record; resolution rechecks current approval and enforces the adapter's declared operation allowlist.
- No dynamic imports, catalogue crawling, provider invocation, network calls, credential handling, or sandboxing were added.
- Added unit tests for approval gating, operation restrictions, revocation, duplicate registration, and invalid contracts.
- Updated the API discovery guide, architecture, roadmap, and test instructions in this change.
- Verification status: pending GitHub Actions until all required workflows pass.

## Prior milestones

The API Discovery Registry was implemented as a SQLite-backed metadata catalogue with URL validation, pricing/licence/verification/approval states, review gates, and audit history. Candidate lifecycle endpoints are connected to the local JSON API. The registry does not import the API-mega-list contents or call third-party providers.

Durable checkpoints, schema migrations, worker leases, and task-attempt records were added in earlier commits. The interrupted-job endpoint remains observational. A STARTED task attempt after a crash is potentially uncertain and must be reconciled before retry; these primitives do not guarantee exactly-once execution.

The project documentation standard requires every implementation milestone to update the relevant architecture, roadmap, development log, and test instructions in the same change. The CI workflow must remain green; tests must not be weakened to hide failures.
