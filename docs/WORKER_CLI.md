# Read-only Worker CLI

Status: **implemented locally as an operator interface; CI verification pending for the commit that introduced it**.

The CLI makes persisted job state easier to inspect without opening SQLite manually. It is intentionally read-only. It does not acquire a lease, execute a task, change job state, resume a failed attempt, or call an AI provider.

## Commands

Run commands from the repository root with Python 3.11 or newer:

```sh
PYTHONPATH=src python -m software_factory.worker_cli --database data/factory.sqlite3 list
PYTHONPATH=src python -m software_factory.worker_cli --database data/factory.sqlite3 list --project-id <project-id>
PYTHONPATH=src python -m software_factory.worker_cli --database data/factory.sqlite3 status <job-id>
```

The database option must come before the subcommand.

## Output and privacy

The commands emit JSON suitable for a terminal or later automation. Summaries include job and project IDs, lifecycle state, timestamps, task counts, completed-task counts, and attempt counts grouped by status.

They intentionally omit specification bodies, task descriptions and inputs, task outputs, lease tokens, and credentials. Do not add those fields to the summary without a separate privacy review.

Exit codes:
- `0`: command completed successfully.
- `2`: the requested job does not exist.
- Argument errors use the standard non-zero exit behaviour from Python's argument parser.

## Limitations

This is an inspection surface, not a worker runner. It does not prove that a task is correct, that generated artifacts pass tests, or that a job is safe to execute. Use the existing independent verification and human-review gates. The SQLite database must be accessible to the process running the command.

## Tests

```sh
PYTHONPATH=src python -m unittest discover -s tests -p 'test_worker_cli.py' -v
```
