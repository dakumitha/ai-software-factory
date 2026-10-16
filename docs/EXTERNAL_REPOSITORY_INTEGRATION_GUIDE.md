# External Repository Integration Guide

This guide records how selected open-source projects fit into the AI Software Factory. It deliberately distinguishes **documented configuration**, **accepted workflow references**, **candidate integrations**, and **working integrations**. A row in the manifest is not proof that software has been installed or connected.

Machine-readable source of truth: [`config/integrations/repositories.json`](../config/integrations/repositories.json).

## Architecture boundary

The factory remains the control plane. It owns project records, specifications, task state, budgets, approvals, audit events, verification evidence and release decisions. External tools may provide documentation, context, proposed code, memory recall or security findings. They do not get authority to change the factory's policy or mark their own output as verified.

```text
Phone / browser
      |
Factory control plane (SQLite, API, jobs, approvals, audit)
      |
      +-- Engineering workflow guidance: Agent Skills
      +-- Library documentation: Context7 MCP (optional)
      +-- Codebase graph: Graphify (optional analysis)
      +-- UI component discovery: 21st MCP (optional)
      +-- Security assessment: Strix (opt-in, cost-gated)
      +-- Long-term memory: Hindsight (future adapter)
      +-- Coding worker: OpenHands SDK (future adapter)
      +-- Separate workspace option: Odysseus (not embedded)
      |
Independent tests + security/licence checks
      |
Human review and explicit release approval
```

## Integration sequence

### 1. Adopt selected engineering workflows first

Upstream: [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills), MIT according to its README.

Start by using the requirements-interview, specification/acceptance-criteria, test-driven-development and code-review workflows as reviewed guidance. Do not blindly install every skill or let a skill replace repository rules. Copy individual skill files only after reviewing the exact upstream revision, recording its source and preserving required attribution. The factory's own tests and acceptance criteria remain the final authority.

### 2. Add optional library-documentation lookup

Upstream: [upstash/context7](https://github.com/upstash/context7), MIT according to its repository metadata.

Context7 is a documentation lookup tool, not a coding agent or execution worker. Current upstream instructions describe a remote MCP endpoint and a local Node.js package. Basic remote use may be available without a key but is rate-limited; check current terms before relying on it. Keep the tool optional so core tests run offline.

Example client configuration for an MCP client that supports remote HTTP servers:

```json
{
  "mcpServers": {
    "context7": {
      "type": "http",
      "url": "https://mcp.context7.com/mcp"
    }
  }
}
```

Some clients use a different schema. Use the client's current documentation rather than copying this example blindly. If an API key is used, store it as `CONTEXT7_API_KEY` in the client's secret/environment configuration. Never commit a real key.

### 3. Evaluate Graphify on a read-only checkout

Upstream: [Graphify](https://github.com/Graphify-Labs/graphify).

Use it to test whether a queryable graph of this repository improves code navigation. Before adoption, pin a reviewed commit, inspect the licence and dependency tree, check supported file types, exclude secrets and generated artifacts, and compare its answers with manual source inspection. Do not make core tests or builds depend on graph generation. No installation or graph generation is claimed by this document.

### 4. Keep UI discovery optional

Upstream: [21st MCP](https://github.com/21st-dev/magic-mcp). The upstream README says the old Magic MCP has been superseded by the unified 21st MCP. Component discovery and hosted AI generation have different eligibility/usage rules. If enabled, configure the API key in the MCP client's secret store as `API_KEY_21ST`; never commit it. Retrieved components are untrusted code and require licence, accessibility, dependency and security review.

Do not make the free software-factory core depend on hosted UI generation.

### 5. Security testing through Strix, only with an explicit gate

Upstream: [usestrix/strix](https://github.com/usestrix/strix).

Strix's current README lists Docker and an LLM provider key as prerequisites. Therefore it is not automatically a zero-cost CI dependency. Keep it opt-in until a known no-cost inference route and resource limits are proven. Run only against repositories and targets the operator is authorized to assess. Use disposable workspaces, retain evidence, manually triage findings, and never auto-merge generated fixes.

### 6. Keep Hindsight behind a future memory interface

Upstream: [vectorize-io/hindsight](https://github.com/vectorize-io/hindsight), MIT according to its README.

Hindsight may be evaluated as a memory service after the factory has a stable memory interface. Its self-hosted deployment still needs compute/storage and a configured model route; the hosted service is usage-based. The existing SQLite job/event history remains the system of record. Memory results are advisory only, and adoption requires retention, deletion, export, tenant isolation and sensitive-data tests.

### 7. Do not embed Odysseus into the core

Upstream: [odysseus-dev/odysseus](https://github.com/odysseus-dev/odysseus), AGPL-3.0-or-later according to its README.

Odysseus is a separate self-hosted AI workspace with powerful local tools. Evaluate it only as a separately deployed interface/agent workspace. Do not vendor or embed it without a licence review. Pin an immutable release and audit authentication, shell/file access, network access and SSRF mitigations before any network-accessible test. Keep its service ports private.

### 8. OpenHands remains a worker candidate, not the control plane

Upstream: [OpenHands Software Agent SDK](https://github.com/OpenHands/software-agent-sdk).

Do not add a mandatory dependency yet. First define a narrow worker interface and test it with a deterministic fake worker. Only then evaluate an exact pinned version in a disposable workspace. Prove the real model route, zero-spend behavior, filesystem/network isolation, timeouts, cancellation, bounded output, checkpoint recovery and independent verification. An SDK or workspace API is not itself proof of a secure sandbox.

## What is and is not integrated today

- The repository manifest records these candidate roles, cost assumptions and safety gates.
- The existing SQLite control plane and API Discovery Registry remain the implementation authority.
- Context7 and 21st have example configuration guidance only. They are **not connected** to the running app.
- Agent Skills are accepted as reviewed workflow references, but no upstream skill files have been copied into this repository by this change.
- Graphify, Strix, Hindsight, Odysseus and OpenHands have **not** been installed, executed or verified as working integrations.
- No paid API, external service, model endpoint, container image or hosted runtime has been activated by this change.

## Acceptance checklist for each real integration

- [ ] Pin the exact repository commit or immutable release.
- [ ] Review the licence and dependency notices.
- [ ] Record runtime, network, data-handling, model and cost requirements.
- [ ] Keep credentials outside Git and logs.
- [ ] Add an adapter behind a stable interface; preserve the model-free core.
- [ ] Add deterministic tests with a fake/offline implementation.
- [ ] Add integration tests that can be explicitly skipped when optional dependencies are absent.
- [ ] Verify timeouts, cancellation, bounded output, failure recovery and audit evidence.
- [ ] Demonstrate that budget, approval and release policies cannot be bypassed.
- [ ] Run targeted CI and record its actual result before changing the status to Integrated or Verified.

## Research sources

- [Agent Skills](https://github.com/addyosmani/agent-skills)
- [Context7](https://github.com/upstash/context7)
- [Graphify](https://github.com/Graphify-Labs/graphify)
- [21st MCP](https://github.com/21st-dev/magic-mcp)
- [Strix](https://github.com/usestrix/strix)
- [Hindsight](https://github.com/vectorize-io/hindsight)
- [Odysseus](https://github.com/odysseus-dev/odysseus)
- [OpenHands Software Agent SDK](https://github.com/OpenHands/software-agent-sdk)
