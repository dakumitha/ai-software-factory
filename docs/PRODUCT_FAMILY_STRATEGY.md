# Multi-Product Software Factory Strategy

## Mission

Build a general-purpose, cloud-first software production engine that can help create and maintain substantial applications across different product families, rather than a one-off generator for a single application.

Long-term target families include:
- Publishing and audience platforms: newsletter publishing, subscriptions, editorial workflows, audience segmentation, email delivery integrations, analytics, monetization and community.
- Commerce marketplaces: customer storefronts, seller operations, catalog/search, pricing, inventory, carts, orders, payments, fulfilment, returns, fraud controls and administration.
- Travel and accommodation marketplaces: listings, availability, calendars, reservations, cancellations, host/guest workflows, reviews, payouts, dispute handling, search and trust/safety.
- Business and productivity software: workflow tools, document systems, finance operations, dashboards, collaboration, APIs and integrations.

These are long-term product families, not claims that the current repository already implements these applications.

## The factory must be product-agnostic

The factory owns the engineering lifecycle and policy:
1. Capture an idea and clarify ambiguous requirements.
2. Convert requirements into versioned specifications and measurable acceptance criteria.
3. Produce architecture, threat models, data models, interface contracts and dependency-aware task plans.
4. Require explicit approval for consequential execution.
5. Delegate bounded tasks to replaceable model/agent providers.
6. Apply generated changes in isolated, disposable workspaces.
7. Run reproducible tests, builds, static analysis, dependency/licence checks and security checks.
8. Collect immutable logs, diffs, artifacts and verification evidence.
9. Repair failures within configured retry and resource budgets.
10. Request human review and explicit release approval.
11. Deploy through configured providers, verify health, and support rollback.
12. Persist state so work can resume safely after interruptions.

Product-specific logic belongs in versioned templates, modules and integration adapters, not in the core orchestration engine.

## Reusable platform capabilities

The factory should build a shared capability library rather than duplicate these concerns for every product:
- Identity, sessions, roles, permissions and tenant boundaries.
- Relational data modelling, migrations and backup/restore checks.
- API contracts, pagination, idempotency, rate limits and webhooks.
- Background jobs, queues, retries, scheduling and dead-letter handling.
- Billing adapters, subscription lifecycle and reconciliation.
- Search, media storage, caching and observability.
- Notifications, email delivery adapters and preference/suppression management.
- Audit trails, privacy controls, retention and export/delete workflows.
- Accessibility, localization, currencies, time zones and responsive UX.
- Threat modelling, secrets handling, dependency review and software supply-chain evidence.
- CI, deployment environments, health checks, rollback and incident runbooks.

Reusable does not mean one implementation is automatically suitable for every workload. Each capability needs explicit contracts, security boundaries, scale assumptions and acceptance tests.

## Product-template contract

Every template should declare:
- Product family and supported user roles.
- Features included and explicitly excluded.
- Runtime, frameworks and supported deployment targets.
- Data model and migration strategy.
- External services, credentials and estimated usage costs.
- Security/privacy assumptions and threat model.
- Required environment variables without embedding secret values.
- Unit, integration, end-to-end, accessibility and security checks.
- Seed/demo data clearly separated from production data.
- Deployment, health-check, backup, restore and rollback instructions.
- Known limits, upstream licences and maintenance status.

Templates and third-party repositories are untrusted until pinned and reviewed. Do not execute untrusted code during metadata evaluation.

## Required engineering rules

- A generated file is not evidence that a feature works.
- A passing unit test is not evidence of production-scale capacity.
- A digest check proves file identity only when the expected digest is trusted; it does not prove correctness or safety.
- External side effects such as sending email, charging payments, booking inventory or issuing refunds need idempotency, reconciliation and explicit authorization.
- Never promise exactly-once external effects without a defensible protocol and provider support.
- Do not claim delivery-rate, throughput, uptime, security, legal compliance or scalability targets without representative measurements and evidence.
- Treat generated code, prompts, repository contents and plugins as untrusted inputs.
- Do not expose credentials or run generated code with unrestricted host permissions.
- Respect provider terms, quotas, data-processing rules and licence obligations.
- Free-tier quotas are limited and can change. Pause on budget/quota exhaustion rather than silently spending money.

## Scale and reliability gates

A template cannot be labelled production-ready solely because CI passes. Depending on the product, its release evidence may need:
- Representative load and soak tests with stated hardware and workload.
- Failure injection and recovery exercises.
- Backup restoration and data-integrity verification.
- Authentication, authorization and tenant-isolation tests.
- Dependency, secret, static-analysis and dynamic-security scans.
- API compatibility and migration tests.
- Accessibility and browser/device coverage.
- Provider quota and cost modelling.
- Operational dashboards, alerts, runbooks and rollback rehearsal.
- Privacy, legal and domain-specialist review where applicable.

Record the test environment and limits alongside every result. Do not extrapolate benchmark results beyond their tested conditions.

## Delivery sequence

### Stage A: Prove the engineering loop
- Connect approved specifications to deterministic task execution.
- Add one-step execution/status CLI and a complete, reproducible demo.
- Produce artifacts and verification reports with durable task history.

### Stage B: Safe coding agent
- Add a provider-neutral model/agent interface.
- Add isolated workspaces, explicit command allowlists, resource/network policy and secret redaction.
- Save diffs, test output, budget events and repair attempts.
- Stop safely on quota exhaustion and ambiguous external side effects.

### Stage C: Independent verification and recovery
- Run builds and tests outside the agent's own claims.
- Add bounded repair loops, retry policy, crash recovery and reconciliation for uncertain attempts.
- Require human review for risky changes and releases.

### Stage D: Reusable application template
- Deliver one small full-stack reference app with database, authentication, API, UI, tests, CI and deployment instructions.
- Prove that the factory can modify the app, run checks, report failures and produce a reviewable patch.
- Do not start multiple massive product templates before this loop is reliable.

### Stage E: Expand product families
Recommended order:
1. A modest publishing/newsletter application using an established email provider.
2. A limited commerce marketplace with a narrow catalogue and fulfilment scope.
3. A limited booking marketplace with availability and reservation consistency.
4. Expand advanced monetization, logistics, recommendation, community and analytics features based on measured demand and capacity.

This order is a pragmatic sequence, not a claim that one product family is inherently easy.

## Current state (2026-10-16)

Implemented foundations include the Python/SQLite control plane, versioned specifications, deterministic task planning, durable task attempts/checkpoints, leases, a trusted-handler execution prototype, bounded artifact writing and non-executing artifact checks.

Not yet implemented or verified: model/agent integration, isolated generated-code execution, independent build/test orchestration, automatic repair/recovery, hosted control-room UI, deployment/rollback automation and a complete generated application.

The immediate milestone remains the smallest reproducible end-to-end vertical slice. This strategy must not be read as evidence that the long-term capabilities already exist.
