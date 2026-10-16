# Free-First Agent Engine Integration Plan

## Decision

Build the factory by integrating proven open-source components behind replaceable interfaces, while keeping the existing deterministic control plane as the authority for state, permissions, budgets, approvals, retries, audit records and releases.

The first coding-agent candidate to evaluate is the [OpenHands Software Agent SDK](https://github.com/OpenHands/software-agent-sdk), which is MIT-licensed and offers Python, TypeScript and REST interfaces for coding agents and ephemeral workspaces. It is a candidate, not yet an adopted runtime. Review the pinned revision, license, dependencies, model compatibility, workspace isolation, data flow, operational requirements and resource use before integration.

Potential future components:
- **OpenHands SDK:** bounded coding-worker adapter, only after the free/local path and isolation requirements are proven.
- **GitHub Actions:** public-repository CI and small reproducible checks. Use targeted workflows and avoid wasteful reruns.
- **Existing factory core:** durable project/spec/task/lease/attempt/event records, deterministic orchestration, approval and budget policy.
- **Temporal or another workflow engine:** evaluate only if persisted SQLite workflows become insufficient. Do not add operational complexity or hosted-service charges prematurely.
- **Model providers:** provider-neutral adapter. Prefer genuinely free local/open-weight inference where practical or a verified no-cost API quota. Never assume a provider's free tier is permanent or sufficient.

## Non-negotiable zero-spend policy

The default permitted spend is **₹0 / US$0**. The system must not silently switch to paid services.

1. No paid model API, hosted agent runtime, cloud VM, database, storage, domain, observability plan, or deployment service without explicit user approval.
2. Keep credentials absent by default. Never ask the agent to discover, print, commit, or log secrets.
3. Record provider, model, quota source, estimated/observed usage, limits and date checked for every external model route.
4. Before a request, check the configured budget. If cost is unknown, billing is enabled, or free quota cannot be confirmed, block the request or require a human decision.
5. On quota/rate-limit exhaustion, checkpoint and pause. Do not automatically retry in a way that can consume paid usage.
6. Provide deterministic no-model tasks and tests so core development can continue without an LLM.
7. Prefer public GitHub repositories and standard GitHub-hosted runners for CI when appropriate. Public-repository standard runner use is free under GitHub's published policy, but larger runners, third-party services, model inference and other cloud services may cost money. Recheck current terms before relying on any quota.
8. Never describe the whole factory as unlimited-free. Open-source software does not provide free compute, model inference, bandwidth or operational reliability by itself.

## Architecture and trust boundaries

The control plane remains authoritative:

`Idea → Clarified spec → Versioned plan → Human approval → Budget check → Isolated worker → Independent checks → Evidence → Human review → Approved release`

The model is a fallible worker, not the scheduler or security authority. It may propose plans and diffs, but cannot approve its own work, alter budgets, grant permissions, mark verification successful, or deploy to production.

Before any agent can edit code or run commands:
- Use a disposable, least-privilege workspace with no production credentials.
- Allowlist tool operations and command classes; never interpret task text as shell code.
- Enforce CPU, memory, wall-clock, output-size, network and retry limits where the runtime supports them.
- Capture task input hashes, model/provider identity, workspace revision, patch/diff, command summaries, logs, exit statuses and verification evidence.
- Keep external side effects behind explicit adapters with idempotency keys and reconciliation.
- Do not automatically replay an interrupted attempt if it may have caused side effects. Mark it uncertain and require reconciliation.
- Verify changes independently with tests, build, static analysis, dependency/licence checks and security checks appropriate to the template.
- Require explicit approval for merging, deploying, spending, or changing production data.

An SDK workspace feature is not by itself proof of a secure sandbox. Verify the actual runtime and network/filesystem boundaries before trusting it with untrusted code.

## Cloud-first, phone-first, no personal-computer dependency

The owner's phone should be sufficient to submit ideas, read plans, approve bounded tasks, inspect logs and review diffs through a mobile-friendly hosted interface when a genuinely free hosting option is available. The phone is a control surface, not the build machine.

Until an authenticated hosted control room and isolated remote worker exist, the current local HTTP API is not remotely accessible safely and must not be exposed directly to the public internet. A public GitHub repository and CI can provide some cloud execution, but do not equal a persistent general-purpose cloud computer. Never claim remote execution is working until a real end-to-end run proves it.

## Adoption gates for OpenHands SDK

Do not add it as a mandatory dependency until all gates pass:
1. Pin an exact reviewed version/commit and confirm its license and transitive dependency licenses.
2. Run a minimal integration in a disposable branch/workspace with no secrets and no production access.
3. Prove a no-cost model route or local inference path works under the user's actual constraints. If none is available, keep the integration optional and the core model-free.
4. Demonstrate task timeout, cancellation, output caps, crash recovery and uncertain-attempt handling.
5. Prove that generated changes cannot bypass the factory's approval, budget, audit and verification gates.
6. Measure the GitHub Actions minutes and any other resource use; stop if a free quota is exhausted.
7. Document exact setup steps, limitations, cleanup, and how to disable the adapter.

## Staged implementation

### Stage 1: free deterministic vertical slice
Complete a small end-to-end example with no LLM: approved spec, task graph, allowlisted deterministic handler, artifact output, independent artifact verification, durable evidence and a human-readable report. Add targeted tests and retain all existing quality gates.

### Stage 2: optional agent adapter
Define a narrow agent-worker protocol and fake worker for tests. Add the OpenHands adapter only after adoption gates pass. Keep the core install and tests usable without OpenHands or model credentials.

### Stage 3: isolated execution and verification
Use a reviewed disposable execution backend; add resource limits, command policy, patch capture, independent tests and security checks. Never run arbitrary model-generated code in the control-plane process.

### Stage 4: mobile control room
Add authenticated project/task/status views, approvals, logs, diffs and budget status. Do not expose the development API publicly without authentication, TLS and hardened deployment configuration.

### Stage 5: product templates
Start with a small newsletter/publishing product, then a constrained commerce marketplace, then a constrained booking marketplace. Reuse shared capabilities, but do not claim Amazon/Flipkart/beehiiv/Airbnb parity until feature-by-feature acceptance criteria and operational evidence support it.

## Current reality

The repository already has a useful deterministic foundation: persisted projects/jobs, versioned specifications, task graphs, leases, durable attempts, recovery inventory, bounded artifact writing and non-executing artifact checks. It does **not** yet have an LLM agent integration, secure isolated executor, hosted mobile control room, automatic repair loop, production deployment/rollback, or a demonstrated free remote runtime. This plan must not be mistaken for implementation of those capabilities.

## References

- OpenHands Software Agent SDK: https://github.com/OpenHands/software-agent-sdk
- OpenHands SDK introduction: https://www.openhands.dev/blog/introducing-the-openhands-software-agent-sdk
- GitHub Actions billing and free-use conditions: https://docs.github.com/en/billing/concepts/product-billing/github-actions
