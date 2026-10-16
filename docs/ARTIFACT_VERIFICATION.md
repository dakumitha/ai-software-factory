# Artifact Verification Evidence

Status: **implemented non-executing file verification**. This is an initial evidence step, not an independent code-quality or security verifier.

## Checks performed

- Ensures the relative artifact path remains inside the configured workspace and refuses symlink components.
- Enforces a 1,000,000-byte maximum read.
- Computes SHA-256 and can compare it with an expected digest.
- Optionally validates UTF-8 JSON syntax.
- Produces a structured JSON report with individual check results and limitations.
- Can save the report through the bounded artifact writer.

## Example

```python
from software_factory.verification import verify_artifact, save_verification_report

evidence = verify_artifact(
    "./private-workspace",
    "reports/plan.json",
    require_json=True,
)
save_verification_report("./private-workspace", "evidence/plan-verification.json", evidence)
print(evidence["status"])
```

A digest match proves that bytes match the supplied digest, not that the expected digest is trustworthy. Valid JSON does not prove the content is correct. The verifier does not run tests, compilers, shell commands, source code, or binaries. Do not interpret PASSED as release approval.

## Tests

```sh
PYTHONPATH=src python -m unittest discover -s tests -p 'test_verification.py' -v
```
