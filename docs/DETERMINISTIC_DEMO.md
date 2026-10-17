# Deterministic Control-Plane Demo

**Status:** Implemented in code; remote CI verification required.

The demo exercises a narrow, repeatable slice of the factory without requiring an API key, external service, network call, or generated-code execution.

## Run it

From the repository root with Python 3.11 or newer:

```sh
PYTHONPATH=src python -m software_factory --demo
```

The command prints a JSON report. It creates its SQLite database in a temporary directory, so the sample project and job do not pollute the normal `data/factory.sqlite3` database.

## What the demo exercises

1. Create a disposable project.
2. Validate and save a versioned specification.
3. Approve the specification only when there are no open questions.
4. Create a deterministic dependency-aware task plan.
5. Move the job through the allowed planning and approval states.
6. Acquire a time-limited worker lease.
7. Record bounded, deterministic dry-run task attempts and checkpoints.
8. Release the lease and move the job to `VERIFYING`, then `REVIEW_REQUIRED`.

## What it deliberately does not do

- It does not call an AI model or an external API.
- It does not invoke a shell or run generated source code.
- It does not claim the planned acceptance criteria have passed. The handler records how many checks were planned; it does not execute them.
- It does not release the job or claim production readiness.

The final state is `REVIEW_REQUIRED` because independent verification and human review are separate gates, not something a successful demo handler can bypass.

## Test it

```sh
PYTHONPATH=src python -m unittest discover -s tests -p 'test_demo.py' -v
PYTHONPATH=src python -m unittest discover -s tests -v
```

The first command targets the demo regression tests. The second runs the repository's full standard-library unittest suite. A command shown here is a documented instruction, not evidence that it has already passed. Check the corresponding GitHub Actions run for actual verification evidence.
