# Tests and Recovery Verification

Run the full standard-library test suite from the repository root:

```sh
PYTHONPATH=src python -m unittest discover -s tests -v
```

Targeted tests:

```sh
PYTHONPATH=src python -m unittest discover -s tests -p 'test_execution.py' -v
PYTHONPATH=src python -m unittest discover -s tests -p 'test_artifacts.py' -v
PYTHONPATH=src python -m unittest discover -s tests -p 'test_verification.py' -v
```

Coverage includes persistence/migrations, lifecycle and task graph validation, specifications/planning, API registry lifecycle, repository metadata evaluation, worker leases, task attempts, deterministic handler execution, bounded artifact writes, and non-executing artifact verification.

The execution controller only invokes explicitly registered trusted handlers. It does not sandbox code, execute shell commands, load plugins, or invoke model APIs. Artifact storage and verification are not a sandbox; use a private workspace and treat generated files as untrusted. Crashed or uncertain attempts require review before replay.
