# Documentation Standard and Change Workflow

**Status:** Required engineering practice  
**Applies to:** Every feature, bug fix, refactor, dependency change, security change, workflow change, and release.

## 1. The rule

Documentation is developed alongside the product, not written once at project start and not postponed until the end. Every code change must update the documentation affected by that change in the same pull request or commit series.

A change is not considered complete merely because the code compiles or tests pass. The relevant user, developer, operator, security, and testing documentation must also be accurate.

## 2. Required sequence for each change

1. **Describe the problem:** update or reference a requirement, issue, or acceptance criterion.
2. **Design the change:** record interfaces, data changes, dependencies, trust boundaries, trade-offs, and failure behaviour. Add an Architecture Decision Record when the decision is consequential.
3. **Implement:** document public interfaces and non-obvious behaviour as the code is written.
4. **Test:** add tests and document how to run them, what they prove, and what remains untested.
5. **Update operator/user guidance:** update setup, configuration, API, troubleshooting, recovery, or user instructions affected by the change.
6. **Record evidence:** note the CI result and commit/PR reference in the development log when a meaningful milestone is reached. Never record a check as passing without actual evidence.
7. **Review consistency:** ensure docs do not claim features, integrations, security controls, or deployment states that are not implemented and verified.

## 3. Which documentation to update

| Change type | Required documentation to consider |
| --- | --- |
| New feature | Product vision/requirements, feature guide, API contract, architecture, tests, roadmap |
| API change | Endpoint reference, request/response examples, error codes, authentication and compatibility notes |
| Database/schema change | Data model, migration and rollback notes, backup/restore, compatibility and recovery tests |
| Job/task lifecycle change | State diagram, allowed transitions, retry/idempotency, pause/resume and failure recovery |
| Model/agent/provider integration | Integration register, setup, quotas/cost, data handling, permissions, fallback and licence |
| Security change | Security policy, trust boundaries, threat model, secret handling and relevant tests |
| Build/CI change | Workflow documentation, permissions, triggers, quota impact and failure diagnosis |
| UI/UX change | User guide, navigation/workflow, accessibility and mobile behaviour |
| Release/deployment change | Deployment/runbook, environment configuration, health checks, rollback and verified evidence |
| Bug fix/refactor | Relevant module/API docs, regression test, limitations if any, and development log for significant milestones |

If a row is not applicable, the change description should briefly say why. Do not create empty documentation just to satisfy a checklist.

## 4. Code-level documentation

- Use clear names and small functions before adding comments that merely repeat the code.
- Document public APIs, configuration values, data contracts, important invariants, exceptions, security-sensitive operations, and non-obvious algorithms.
- Explain *why* a surprising choice exists, not every obvious line.
- Include type hints and docstrings where they improve the Python interface.
- Keep examples runnable where practical and label pseudocode or illustrative examples clearly.
- Never put secrets, personal data, access tokens, or confidential production values in docs, tests, examples, logs, or commit history.

## 5. Accuracy and status labels

Use explicit status labels such as **Implemented**, **Partially implemented**, **Proposed**, **Verified in CI**, **Not verified**, and **Blocked**.

A green CI run proves only the checks that workflow actually ran. It does not prove production readiness, successful deployment, complete security, or universal compatibility.

External tools must not be described as integrated until an adapter exists and an end-to-end test demonstrates it. Free-tier availability, quotas, model access, and licences must be verified rather than assumed.

## 6. Documentation quality gate

Before a change is ready for review, confirm:

- [ ] Requirements and acceptance criteria match the change.
- [ ] Affected architecture/API/data contracts are documented.
- [ ] Tests and test instructions are updated.
- [ ] User/operator setup and failure-recovery guidance is accurate.
- [ ] Security, privacy, licence, and cost implications are considered.
- [ ] Roadmap and integration status reflect reality.
- [ ] Development log records meaningful milestone evidence without unsupported claims.
- [ ] No documentation describes a proposed capability as implemented.

The repository's documentation CI checks that core documents exist and are non-empty. This is a basic safeguard, not an automated proof that the documentation is complete or correct. Human review remains necessary.

## 7. Required documents by lifecycle stage

### Before implementation
- Product requirement and acceptance criteria
- Architecture/interface notes
- Security, privacy, licence and budget implications
- Decision record when warranted

### During implementation
- Module/API/docstrings and examples
- Data/schema/migration notes
- Test cases and developer instructions
- Updated integration status

### Before release
- User and operator instructions
- Deployment configuration and secrets guidance
- Test evidence and known limitations
- Recovery, backup, rollback and support instructions
- Release notes and explicit approval record

## 8. Ownership and enforcement

The author of a change is responsible for its documentation. Reviewers should reject changes whose documentation is missing, stale, or misleading. Documentation updates belong in the same change as the implementation; they should not be deferred to a future cleanup milestone.

This standard evolves with the project. If the workflow changes, update this document and its CI checks in the same change.
