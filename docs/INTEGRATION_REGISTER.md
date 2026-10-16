# Integration Register and Audit Rules

This register is the source of truth for candidate repositories and tools. A candidate is not approved merely because it is public or popular.

## Status vocabulary

- **Candidate**: identified, not yet audited.
- **Auditing**: source, licence, activity, dependencies, security, interface and runtime are being checked.
- **Accepted**: evidence supports a bounded use with recorded constraints.
- **Rejected**: material incompatibility, unacceptable risk, licence conflict, or no credible operational path.
- **Integrated**: implemented adapter or component with tests and documented configuration.
- **Verified**: integration passed its specified end-to-end checks in the target environment.

## Initial candidates

| Candidate | Potential role | Current status | Required checks |
|---|---|---|---|
| GitHub Spec Kit | Spec-driven requirements and planning workflow | Candidate | Licence, supported workflow, CLI/runtime requirements, compatibility with desired agent setup |
| OpenHands | Coding agent runtime/orchestration | Candidate | Licence, sandbox model, resource needs, supported inference providers, host compatibility, security posture |
| LangGraph | Durable orchestration and checkpoint concepts | Candidate | Licence, persistence backend, operational complexity, fit versus simpler state machine |
| OpenSpec | Specification/change-management workflow | Candidate | Licence, overlap with Spec Kit, maintenance, migration/interoperability |
| Graphiti | Temporal/knowledge graph memory | Candidate | Licence, database and service requirements, necessity versus simpler relational/event storage |
| Arize Phoenix | LLM tracing/evaluation | Candidate | Licence, hosting/storage footprint, data privacy, free-tier or self-host cost |
| Graphify | Codebase graph/context | Candidate | Exact repository and licence, maintenance, language support, measured value on representative repositories |
| REA (`morluto/rea`) | Possible agent-workflow integration | Candidate | Inspect exact source, licence, setup, permissions, runtime and threat surface before executing |

This is an initial shortlist, not a claim that these components have been installed or proven compatible. More candidates may be added after focused GitHub discovery.

## Audit checklist

For each candidate, record:
1. Canonical repository URL and exact commit/tag reviewed.
2. Licence and obligations, including transitive dependencies.
3. Last meaningful release/commit and maintenance signals.
4. Open critical/high security advisories where discoverable.
5. Supported languages, interfaces, and integration mechanism.
6. Runtime, compute, storage, network, and credential requirements.
7. Free-tier fit and whether operation depends on paid model APIs.
8. Container/sandbox and privilege assumptions.
9. Data collection, telemetry, retention, and privacy behaviour.
10. Test coverage, reproducibility, and compatibility with our target.
11. Decision, rationale, owner, and follow-up date.

## Integration rules

- Do not run install scripts or repository code during initial review.
- Pin accepted integrations to a reviewed commit or release.
- Avoid duplicate frameworks unless a comparative test demonstrates a benefit.
- Prefer stable APIs and small adapters over invasive forks.
- Track licence notices and preserve required attribution.
- Do not send confidential user or project data to external services without explicit configuration and approval.
- Do not integrate a component solely to increase the number of agents.
