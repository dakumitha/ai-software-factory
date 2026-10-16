# Built-in Artifact Task Adapter

## Purpose

This adapter exposes a narrow task contract for creating and checking an artifact. It is an allowlisted handler, not a generic executor. Only the `artifact_integrity` task kind is accepted.

## Payload contract

Required fields: `kind` (exactly `artifact_integrity`), workspace-relative `path`, and `content` (text or bytes). Optional fields: `require_json` (boolean) and workspace-relative `evidence_path`. The underlying writer enforces path checks and the 1 MB size cap. Unknown task kinds are rejected before creating a workspace. Arbitrary command strings are never run.

## Outcome and limits

The handler returns artifact metadata, verification results, and a saved evidence report. It always returns `next_state: REVIEW_REQUIRED`, never releases a job, and never executes generated source. A passing result proves only file integrity and optional JSON syntax.

Run focused tests with `PYTHONPATH=src python -m unittest discover -s tests -p 'test_artifact_task.py' -v`. Check GitHub Actions for the latest commit before treating tests as passed.
