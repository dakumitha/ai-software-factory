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
| [GitHub Spec Kit](https://github.com/github/spec-kit) | Spec-driven requirements and planning workflow | **Auditing** | MIT licence file verified; inspect CLI/runtime, versioned workflows and compatibility before adoption |
| [OpenHands](https://github.com/OpenHands/OpenHands) | Coding-agent control centre / execution integration | **Auditing** | MIT licence file verified; current README highlights Agent Canvas and multiple backends; host/runtime and model costs remain unresolved |
| [OpenSpec](https://github.com/Fission-AI/OpenSpec) | Specification/change-management workflow | **Auditing** | MIT licence file verified; compare against Spec Kit to avoid duplicate process and tooling |
| [LangGraph](https://github.com/langchain-ai/langgraph) | Durable orchestration and checkpoint concepts | Candidate | Licence, persistence backend, operational complexity, fit versus simpler state machine |
| [Graphiti](https://github.com/getzep/graphiti) | Temporal/knowledge graph memory | Candidate | Licence, database and service requirements, necessity versus simpler relational/event storage |
| [Arize Phoenix](https://github.com/Arize-ai/phoenix) | LLM tracing/evaluation | Candidate | Licence, hosting/storage footprint, data privacy, free-tier or self-host cost |
| [Graphify](https://github.com/Graphify-Labs/graphify) | Codebase graph/context | Candidate | Exact repository and licence, maintenance, language support, measured value on representative repositories |
| [REA](https://github.com/morluto/rea) | Specialist reverse-engineering MCP/tools | **Candidate, not core engine** | MIT licence file verified; README describes binary/app/runtime reverse engineering, so include only as an optional specialist tool after threat-surface and need review |

This is an initial shortlist, not a claim that these components have been installed or proven compatible. Focused source inspection on 2026-10-16 verified the visible LICENSE files for Spec Kit, OpenHands, OpenSpec, and REA. This is a preliminary licence-file check only, not a complete legal review, dependency audit, security audit, or compatibility test. More candidates may be added after focused GitHub discovery.

## Preliminary findings (2026-10-16)

- **Do not combine Spec Kit and OpenSpec by default.** Both provide specification-oriented workflows. Compare them on one representative feature and choose one primary workflow to reduce duplicated documents and process overhead.
- **OpenHands is not free compute by itself.** Its repository describes a self-hosted control centre that can connect to different agent backends. A host and an available model/inference route are still required; their free availability and quotas must be verified.
- **REA is not a general software-building engine.** Its README positions it as a reverse-engineering toolset/MCP. Keep it optional for specialised analysis rather than making it a core dependency.
- **No candidate has been installed or executed.** Initial review was limited to repository metadata, README content, and visible LICENSE files.

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
