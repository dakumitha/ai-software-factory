# Deterministic Task Execution Controller

Status: **local prototype**. This adds one small execution loop to the existing persisted job/task workflow. It is not a general-purpose agent, code runner, sandbox, or deployment engine.

## How it works

1. Requires a job in RUNNING or VERIFYING state and a valid, unexpired worker lease.
2. Selects the lexicographically first ready task whose dependencies are in the durable checkpoint.
3. Looks up the task's `type` in an explicitly supplied in-process handler allowlist. Missing handlers are blocked without creating an attempt.
4. Writes a durable task-attempt record before invoking the handler.
5. Invokes one handler with JSON-shaped task input and the job specification. Task title and description are never interpreted as code or shell commands.
6. Checks that output can be JSON-encoded and is no larger than 1 MB.
7. Stores the terminal attempt result and checkpoint progress.

## Use from Python

```python
from software_factory.core import Store
from software_factory.execution import ExecutionController

store = Store("data/factory.sqlite3")
controller = ExecutionController(store, {
    "echo": lambda task: {"received": task["input"]},
})
# The job must already be RUNNING and have a valid worker lease.
result = controller.run_next(job_id, lease_token)
print(result)
```

A handler is trusted application code. This controller does not isolate it, enforce CPU/time limits, restrict file or network access, or prevent a handler from accessing process secrets. Do not register model-generated code or arbitrary repository plugins as handlers. The first intended handlers should be deterministic, narrowly scoped operations such as validating a spec or writing a generated artifact inside an isolated workspace.

## Recovery and side effects

If a process crashes after a handler causes an external side effect but before its terminal result is durably recorded, the side effect may have occurred. The controller must not automatically replay a STARTED attempt. Operator reconciliation and idempotent handler design are required. This prototype records failure if a handler raises; it does not classify arbitrary exceptions as proof that no side effect happened. Treat crashes, lost worker leases, and uncertain external actions as review cases.

## Explicit non-goals

- No shell execution or arbitrary Python evaluation.
- No automatic job state transitions or automatic resume.
- No model-provider API calls, coding agent, hosted worker, UI, or deployment.
- No sandbox guarantees or exactly-once external effects.
- No claim that all tasks complete merely because handlers return successfully. Acceptance checks and independent verification are separate future gates.

## Tests

```sh
PYTHONPATH=src python -m unittest discover -s tests -p 'test_execution.py' -v
```
