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
- **Pending verification:** CI for the checkpoint implementation commit. This is not yet a complete executor, exactly-once guarantee, or full process-crash recovery system.
