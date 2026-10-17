# Artifact Workspace

Status: **implemented bounded local file writer**. This is not a process sandbox or a complete artifact-verification service.

## Behaviour

- Writes text or bytes under an operator-selected workspace.
- Rejects absolute paths, parent traversal, NUL/backslash path forms, and symlink components.
- Limits each artifact to 1,000,000 bytes.
- Does not overwrite existing files unless the caller explicitly passes `overwrite=True`.
- Returns the relative path, byte count, SHA-256 digest, and overwrite flag.
- Supports deterministic JSON output through `write_json_artifact`.
- Creates files with restrictive permissions where supported.

## Example

```python
from software_factory.artifacts import write_json_artifact

receipt = write_json_artifact(
    "./private-workspace",
    "reports/build-plan.json",
    {"status": "planned", "tasks": []},
)
print(receipt)
```

## Security boundary

Use a private workspace owned by the factory. This module reduces common path mistakes but does not defend against every concurrent filesystem race, hostile local process, hard-link attack, disk exhaustion, or malicious handler. Do not store secrets here. Never expose a workspace directly to the public web server. Generated code must not be executed merely because it was written successfully.

## Tests

```sh
PYTHONPATH=src python -m unittest discover -s tests -p 'test_artifacts.py' -v
```
