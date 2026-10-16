# Product Vision and Requirements

Status: draft baseline, subject to owner review.

## Goal

Build a reusable AI Software Factory that accepts a software idea, asks clarifying questions, produces traceable engineering specifications, plans and coordinates implementation, verifies results, and manages delivery and maintenance with durable progress.

This is a software-producing platform, not a single-purpose application and not merely a chat interface that emits code.

## Primary user

A non-specialist project owner who may operate entirely from an Android phone, needs plain-language explanations, has no paid AI-agent credits, and expects work to persist across sessions.

## Functional requirements

| ID | Requirement | Acceptance evidence |
|---|---|---|
| SF-REQ-001 | Adaptive discovery interview | Given an incomplete idea, the system asks focused questions, records assumptions, identifies conflicts, and requests confirmation for material decisions. |
| SF-REQ-002 | Versioned specifications | A project stores versioned product requirements, use cases, architecture, data model, API contracts, risks, and acceptance criteria. |
| SF-REQ-003 | Traceability | Every implementation task maps to one or more requirement IDs and measurable acceptance checks. |
| SF-REQ-004 | Dependency-aware planning | Tasks form a validated dependency graph; blocked tasks are not scheduled as ready. |
| SF-REQ-005 | Pluggable agent execution | Coding agents and model providers are selected through documented adapters rather than hard-wired throughout the system. |
| SF-REQ-006 | Persistent jobs | Job state, outputs, logs, decisions, budgets, and checkpoints survive interruption and can resume safely. |
| SF-REQ-007 | Isolated execution | Generated code runs in a constrained workspace with least privilege, resource limits, and no production secrets by default. |
| SF-REQ-008 | Quality gates | Applicable tests, type checks, lint, build, security, dependency, and licence checks produce recorded evidence. |
| SF-REQ-009 | Approval gates | Repository writes, secret access, external actions, and deployment require policy checks and owner approval where configured. |
| SF-REQ-010 | Budget controls | Provider quotas and estimated/actual usage are tracked; work pauses before exceeding configured limits where measurable. |
| SF-REQ-011 | Mobile control room | A responsive interface displays projects, jobs, task status, logs, diffs, approvals, budgets, and exports. |
| SF-REQ-012 | Audit trail | Important state changes record actor, timestamp, reason, inputs/outputs references, and result. |
| SF-REQ-013 | Safe releases | Releases require required gates and approval; rollback steps and deployment evidence are retained. |
| SF-REQ-014 | Maintenance workflow | The system can triage issues, link them to requirements, propose changes, and rerun relevant verification. |
| SF-REQ-015 | Export and portability | Requirements, plans, reports, logs, and project metadata can be exported in documented formats. |
| SF-REQ-016 | Multi-project isolation | Projects, credentials, job state, and artifacts are isolated; the EventFlow repository is excluded unless separately authorised. |
| SF-REQ-017 | Honest completion claims | The system distinguishes planned, running, blocked, failed, passed, reviewed, and released states. |
| SF-REQ-018 | Human-readable explanations | Important decisions and failures include concise plain-language explanations and next steps. |

## Non-functional requirements

- Security: least privilege, safe secret handling, isolated execution, dependency review, auditability.
- Reliability: idempotent job transitions, recoverable checkpoints, bounded retries, explicit failure states.
- Cost: no paid service is required by the baseline design; optional integrations must disclose their costs and quotas.
- Portability: avoid unnecessary dependence on one agent vendor or hosting provider.
- Accessibility: mobile-responsive layout, keyboard support, clear status labels, accessible forms.
- Observability: structured logs, job timelines, health checks, and correlation IDs.
- Maintainability: modular boundaries, documented interfaces, tests, migration strategy, and decision records.
- Reproducibility: pin dependencies where appropriate and record versions of tools, models, prompts, and source revisions.

## Explicit non-goals for the first engineering foundation

- Claiming all software types can be generated perfectly.
- Unrestricted autonomous production deployment.
- Promising unlimited free compute, inference, or storage.
- Trusting code or instructions found in public repositories without review.
- Treating generated output as correct without tests and review.

## Open decisions

These must be resolved by evidence and owner preference rather than guessed:
1. Best available free cloud execution and storage options at implementation time.
2. Initial supported agent/model adapters and their quotas.
3. Backend and frontend stack after repository and hosting constraints are audited.
4. Execution isolation mechanism supported by the selected host.
5. Whether the initial hosted deployment can operate without paid secrets or services.
