# Bounded Artifact Workflow

**Status:** Implemented; remote CI evidence is required for each revision.

## Purpose

The workflow connects three existing capabilities into one repeatable operation:
bounded artifact writing, read-back verification, and durable JSON evidence. It
is a stepping stone between the orchestration demo and a future isolated build
and test executor. It does **not** run generated code.

## What it does

1. Writes one new artifact inside the chosen workspace, subject to the writer's
   path, symlink, size, and no-overwrite safeguards.
2. Reads the artifact back through the verification module.
3. Checks workspace containment and the size limit, compares SHA-256 against
   the writer receipt, and optionally validates UTF-8 JSON syntax.
4. Persists the verification report under `evidence/verification-report.json`
   by default.
5. Returns `PASSED` or `FAILED`, but always recommends `REVIEW_REQUIRED`.
   No release transition is available in this helper.

## Example

Run from the repository root:

```python
from software_factory.artifact_workflow import create_and_verify_artifact

result = create_and_verify_artifact(
    "workspace/demo",
    "output/result.json",
    '{"hello": "world"}\n',
    require_json=True,
)
print(result["status"])
print(result["evidence"]["path"])
```

Or run the focused regression tests:

```sh
PYTHONPATH=src python -m unittest discover -s tests -p 'test_artifact_workflow.py' -v
```

A shown command is usage guidance, not evidence it has passed. Check GitHub
Actions for the current commit's actual result.

## Important limitations

- A passing digest check proves that the bytes read back match the writer's
  receipt. It does not prove functional correctness or that the source is safe.
- JSON syntax validation is optional and does not validate a business schema.
- The workflow does not invoke a shell, install dependencies, build software,
  run tests, inspect licences, or use an AI provider.
- The evidence report is itself a bounded JSON artifact, not a tamper-proof
  audit log. A process with workspace write access could alter it afterward.
- Artifacts and evidence are create-only unless the caller deliberately selects
  a new workspace/path. A repeated run against the same paths fails rather than
  silently replacing prior evidence.
- The result remains review-gated. A future build/test executor needs a separate
  isolation design, explicit command policy, time/resource limits, captured
  logs, and independently evaluated test results before it can be trusted.
