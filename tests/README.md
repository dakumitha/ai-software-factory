# Tests and Recovery Verification

Run the full standard-library test suite from the repository root:

```sh
PYTHONPATH=src python -m unittest discover -s tests -v
```

Execution-controller tests:

```sh
PYTHONPATH=src python -m unittest discover -s tests -p 'test_execution.py' -v
```

Coverage includes persistence/migrations, lifecycle and task graph validation, specifications/planning, API registry lifecycle, repository metadata evaluation, worker leases, task attempts, and deterministic handler execution.

The execution controller only invokes explicitly registered trusted handlers. It does not sandbox code, execute shell commands, load plugins, or invoke model APIs. Never register model-generated code or arbitrary repository plugins. Crashed or uncertain attempts require review before replay.
