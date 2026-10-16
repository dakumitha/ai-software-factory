# Tests and Recovery Verification

The control plane uses Python's standard library only. Run from the repository root:

```sh
PYTHONPATH=src python -m unittest discover -s tests -v
```

## What the current tests verify

- SQLite project/job persistence after reopening the store.
- Ordered schema migrations, legacy database upgrade without record loss, and migration re-open safety.
- Worker lease acquisition, token-protected heartbeat/release, and recovery inventory filtering for active leases.
- Read-only inventory of RUNNING/VERIFYING jobs for explicit interruption review.
- Validated lifecycle transitions and append-only job event history.
- Task dependency graph validation and ready-task selection.
- Checkpoint persistence across store reopen, task-ID validation, monotonic completed-task tracking, and idempotent repeated writes.
- SQLite online backup and restoration of projects, jobs, checkpoint state, and audit events.
- HTTP API behaviour for projects, jobs, specification approval/planning, and checkpoint updates.

## Checkpoint contract and limitations

A checkpoint stores orchestration progress in the job's SQLite record. `completed_task_ids` must refer to tasks belonging to that job and cannot remove a previously recorded completion. Repeating the exact same checkpoint does not create another audit event.

This is a durable progress ledger, **not yet a complete job executor or exactly-once execution guarantee**. The current application does not execute agent tasks. Before execution is added, each adapter must define idempotency keys, durable task attempt records, interruption recovery, bounded retry behaviour, and verification evidence. A checkpoint must not be treated as proof that generated code passed tests.

The interrupted-job endpoint is intentionally read-only. It excludes unexpired worker leases, but a missing/expired lease does not prove that a worker is dead or resume tasks. Lease tracking is ownership metadata, not a complete executor. The suite does not yet verify hosted deployment, authentication, sandbox isolation, encrypted/remote backup retention, or production crash recovery.

## Creating a database backup

The `Store.backup_to(destination)` method uses SQLite's online backup API to create a consistent copy, including while the database is open. Example from the repository root:

```python
from software_factory.core import Store

store = Store("data/factory.sqlite3")
backup_path = store.backup_to("backups/factory-backup.sqlite3")
print(f"Backup written to: {backup_path}")
```

Protect backups as carefully as the live database. Store them outside public repositories, restrict access, and apply your retention policy. A backup is not proven recoverable until a restore test opens the copied database and checks expected records. This method does not encrypt backups or upload them to remote storage.
