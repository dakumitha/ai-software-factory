# Development Log

This log records meaningful project milestones and verified evidence. It is not a substitute for the Git commit history, test output, issue tracker, or release records.

## 2026-10-16

### Documentation is a continuous engineering requirement
- Added `docs/DOCUMENTATION_STANDARD.md` defining documentation-before/during/after implementation, change-specific update expectations, accuracy labels, and a review checklist.
- Updated the repository README to link the standard and this log.
- Expanded the documentation CI required-file list to include the documentation standard, development log, specification workflow guide, and test instructions.
- Corrected roadmap status for the core-test workflow and API integration tests based on the available GitHub Actions evidence.
- The roadmap explicitly distinguishes selected persistence/store-reopen checks from the still-unproven complete interrupted-job resume and checkpoint-consistency behaviour.
- Verification evidence available before this documentation change: core tests run [38840047085](https://github.com/dakumitha/ai-software-factory/actions/runs/38840047085), specification workflow run [38840047064](https://github.com/dakumitha/ai-software-factory/actions/runs/38840047064), and repository foundation checks run [38840047183](https://github.com/dakumitha/ai-software-factory/actions/runs/38840047183) were reported successful for commit `cc27e543839ece182b45c2447de395ad1e815fe2`.
- Documentation-standard commit CI verified: [Core tests](https://github.com/dakumitha/ai-software-factory/actions/runs/38840251909), [Specification workflow tests](https://github.com/dakumitha/ai-software-factory/actions/runs/38840251866), and [Repository foundation checks](https://github.com/dakumitha/ai-software-factory/actions/runs/38840251925) all completed successfully for commit `0f810efc5cf5753303fcc9923e3109c4e3936a02`.

### Durable checkpoint progress
- Added `Store.save_checkpoint` and `POST /jobs/{job_id}/checkpoint` to persist orchestration progress and record meaningful changes in the job event history.
- Checkpoint validation ensures the current task and completed tasks belong to the job's task graph, completed IDs are unique, and completed-task history cannot regress.
- Identical checkpoint submissions are idempotent and do not add duplicate audit events.
- Added tests for persistence after reopening SQLite, repeated identical writes, unknown task IDs, completion regression, and API behaviour.
- Updated architecture and test instructions to document the checkpoint contract and explicitly state what it does not guarantee.
- Checkpoint implementation CI verified: [Core tests](https://github.com/dakumitha/ai-software-factory/actions/runs/38840675239), [Specification workflow tests](https://github.com/dakumitha/ai-software-factory/actions/runs/38840675240), and [Repository foundation checks](https://github.com/dakumitha/ai-software-factory/actions/runs/38840675265) passed for commit `1f9c6916d767db5e3e63bfe8d6e034c27aa012c7`.
- **Not a complete executor:** exactly-once execution and full process-crash recovery remain unimplemented.

### SQLite backup and restore verification
- Added `Store.backup_to(destination)`, using SQLite's online backup API to make a consistent database copy.
- Added tests that restore a copied database and verify project, job checkpoint, and audit-event records, and that reject the live database as its own backup destination.
- Updated architecture and test instructions with the backup contract, example, and security caveats.
- CI verification for the backup milestone was reported successful for commit `4a594598c334eac66f21f9a9139dbdbe29be735f` (core tests run [38840769733](https://github.com/dakumitha/ai-software-factory/actions/runs/38840769733), specification workflow run [38840769654](https://github.com/dakumitha/ai-software-factory/actions/runs/38840769654), foundation checks run [38840769612](https://github.com/dakumitha/ai-software-factory/actions/runs/38840769612)).

### Schema evolution and interruption inventory
- Added an ordered schema migration ledger. Migration v1 recognises the existing project/job/event schema; v2 adds indexes for job state/update-time and event lookup.
- Opening a pre-migration database records its baseline version and applies later additive migrations without recreating or deleting user records. Databases declaring a newer schema version are refused rather than silently downgraded.
- Added `Store.schema_version()` and tests for migration version recording, repeated initialization, and preserving a legacy project row.
- Added `Store.list_interrupted_jobs()` and `GET /recovery/interrupted` to inventory RUNNING/VERIFYING jobs and checkpoint pointers without mutating job state.
- The recovery endpoint is intentionally observational: without worker leases/heartbeats and durable task-attempt semantics, automatic restart could collide with a still-running worker or repeat side effects.
- Added unit/API coverage and updated architecture, test instructions, and roadmap in the same change.
- First GitHub Actions run exposed a test-fixture reference error (the API test stores its database on `ApiHandler.store`, not `self.store`). The assertion was corrected without changing production behavior.
- The corrected schema-migration and recovery-inventory tests passed in GitHub Actions for commit `fc5cf09354066e76baeb9a9d6d70841d7c052318` (core [38841280562](https://github.com/dakumitha/ai-software-factory/actions/runs/38841280562), spec/API [38841280592](https://github.com/dakumitha/ai-software-factory/actions/runs/38841280592), foundation [38841280573](https://github.com/dakumitha/ai-software-factory/actions/runs/38841280573)).
- Added schema migration v3 for expiring worker leases. Lease tokens are random, returned only at acquisition, and stored as SHA-256 hashes; heartbeat and release require the matching token.
- The interrupted-job inventory now excludes jobs with unexpired leases and surfaces jobs with missing/expired leases for operator review.
- Added store and HTTP API tests for lease acquisition, heartbeat, invalid tokens, release, TTL validation, and recovery-inventory interaction.
- Updated architecture, roadmap, and test instructions in the same implementation cycle.
- Worker-lease migration and API tests passed on commit `a42d0fcd97911c614bd996aa254a4e6080671793` (core [38841399560](https://github.com/dakumitha/ai-software-factory/actions/runs/38841399560), spec [38841399648](https://github.com/dakumitha/ai-software-factory/actions/runs/38841399576), foundation [38841399576](https://github.com/dakumitha/ai-software-factory/actions/runs/38841399576)).
- Added schema migration v4 and durable task-attempt records with idempotency-key uniqueness, input fingerprinting, and terminal status immutability.
- Task attempts require an unexpired worker lease and a known task. A repeated key with identical task/input returns the original attempt; conflicting reuse is rejected.
- Interrupted-job inventory includes a count of attempts still STARTED or marked UNCERTAIN, which need reconciliation before retry.
- Added store/API tests and updated architecture, roadmap, and test instructions in this same change.
- **Pending verification:** GitHub Actions for durable task attempts.
