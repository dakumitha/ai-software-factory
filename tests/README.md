# Tests and Recovery Verification

The control plane uses Python's standard library only. Run from the repository root:

```sh
PYTHONPATH=src python -m unittest discover -s tests -v
```

## What the current tests verify

- SQLite project/job persistence after reopening the store.
- Validated lifecycle transitions and append-only job event history.
- Task dependency graph validation and ready-task selection.
- Checkpoint persistence across store reopen, task-ID validation, monotonic completed-task tracking, and idempotent repeated writes.
- HTTP API behaviour for projects, jobs, specification approval/planning, and checkpoint updates.

## Checkpoint contract and limitations

A checkpoint stores orchestration progress in the job's SQLite record. `completed_task_ids` must refer to tasks belonging to that job and cannot remove a previously recorded completion. Repeating the exact same checkpoint does not create another audit event.

This is a durable progress ledger, **not yet a complete job executor or exactly-once execution guarantee**. The current application does not execute agent tasks. Before execution is added, each adapter must define idempotency keys, durable task attempt records, interruption recovery, bounded retry behaviour, and verification evidence. A checkpoint must not be treated as proof that generated code passed tests.

The suite does not yet verify hosted deployment, authentication, sandbox isolation, database backup/restore, or production crash recovery.
