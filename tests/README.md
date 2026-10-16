# Tests and Recovery Verification

Run from the repository root with Python 3.11+:

```sh
PYTHONPATH=src python -m unittest discover -s tests -v
```

## Coverage

- SQLite project/job persistence, ordered migrations, legacy upgrade, worker leases, and task attempts.
- Read-only interruption inventory, lifecycle transitions, event history, task graph validation, and ready-task selection.
- Checkpoint persistence, task-ID validation, monotonic completion, idempotent writes, and online backup/restore.
- HTTP API behavior for projects, jobs, specifications, checkpoints, and API registry lifecycle.
- API registry URL validation, filtering, review/approval policy, audit events, control-plane integration, and CLI lifecycle commands.
- Adapter registration against approved candidates, operation allowlisting, approval revocation checks, duplicate rejection, and invalid contracts.
- Repository evaluator metadata detection, bounded file reads, JSON report fields, and non-execution guarantees.

## API registry and adapter boundaries

The registry records third-party API metadata only. It does not crawl websites, invoke providers, install dependencies, execute examples, or manage secrets. Approval requires a verified candidate, an approved/not-applicable licence, and known pricing. This policy does not guarantee provider security or future pricing.

The provider adapter interface accepts only explicitly constructed in-process objects. Registration requires an approved record; resolution rechecks current approval and the operation allowlist. It does not invoke providers, sandbox adapter code, manage secrets, or implement network timeouts/rate limits. Control-plane registry endpoints currently have no authentication and must remain loopback-only.

## Repository evaluator boundaries

- Metadata-only inspection of an already-present local repository; bounded reads of recognised files.
- No clone/fetch, dependency installation, package lifecycle execution, imports, tests, or builds.
- Score is not a security rating and cannot approve a repository. All reports remain REVIEW_REQUIRED.
- A detected licence filename does not establish licence identity or dependency compatibility.

See [Repository and Template Evaluator](../docs/REPOSITORY_TEMPLATE_EVALUATOR.md).

## Recovery limits

Checkpoints and task attempts are orchestration metadata, not a complete executor or exactly-once guarantee. A STARTED attempt after a crash may have caused side effects and must be reconciled before retry. Hosted deployment, authentication, sandbox isolation, encrypted/remote backup retention, and production crash recovery are not verified.

## Backup

Store.backup_to(destination) uses SQLite's online backup API. Protect backups, keep them outside public repositories, and test restoration. It does not encrypt or upload them remotely.

## Curated API catalogue import

- `software_factory.catalogue_import` reads local JSON/CSV only. Preview is read-only and default; `--apply` is required to write.
- Only `name`, `category`, `source_url`, and optional `provider_url`, `pricing_status`, `licence_status`, `notes` are accepted. Files are capped at 5,000 rows and validated for HTTPS URLs and duplicates.
- Imported records remain PENDING and UNVERIFIED. No remote fetching, crawling, package installation, sample execution, or provider invocation occurs.
