# Tests

The initial control plane intentionally uses Python's standard library only.

Run from the repository root:

```sh
PYTHONPATH=src python -m unittest discover -s tests -v
```

The tests cover SQLite persistence, validated state transitions, event history,
dependency graph validation, and ready-task selection. They do not yet test
agent execution, hosted deployment, authentication, or generated-code isolation.
