# Phase 1: Hybrid Toolchain Bootstrap

**Status:** in progress  
**Target:** Windows 11 + VS Code on the desktop, with cloud-hosted source control/CI and a phone-friendly control surface.  
**Budget policy:** ₹0 / US$0 by default. No paid API, cloud compute, subscription, deployment, or upgrade is permitted without explicit approval.

## 1. Scope and non-goals

Phase 1 establishes a reproducible developer environment and proves one safe, small coding-agent task from checkout to verified diff. It does not yet enable unattended production deployment, unrestricted shell execution, or a persistent cloud worker.

The existing deterministic Python/SQLite control plane remains authoritative for project/job state, task permissions, quotas, approvals, audit events, and release decisions. EventFlow is explicitly out of scope and must not be modified by this project.

## 2. Target topology

```text
Android phone
  └─ review/status/approval UI (later phase; authenticated only)
       │ HTTPS
Cloud control plane / GitHub
  ├─ GitHub repository: requirements, issues, branches, PRs, CI evidence
  ├─ GitHub Actions: targeted, reproducible CI where free quota permits
  └─ no public unauthenticated worker endpoint
       │
Windows 11 workstation (primary development and local compute)
  ├─ VS Code + Git
  ├─ Claude Code (coding harness; provider/account cost must be verified)
  ├─ ECC (engineering workflow plugin)
  ├─ Ponytail (minimal-change/reuse skill; not a model or orchestrator)
  ├─ Graphify (optional read-only code knowledge graph)
  ├─ REA bridge (existing reverse-engineering-to-specification module)
  ├─ Docker (only for explicitly approved isolated tools such as Strix)
  └─ local model runtime (optional; hardware and model fit to be benchmarked)
       │
Model gateway: select ONE primary gateway for the first experiment
  ├─ FreeLLMAPI: local-first unified API and provider fallback
  └─ OmniRoute: alternative local/remote model router
       │
Providers
  ├─ local inference where practical
  └─ verified free quota only; paid routes blocked by default
```

The phone is a control surface, not the build machine. The Windows workstation or a separately verified free runner performs compute. A GitHub repository and CI runner do not constitute a persistent general-purpose cloud computer.

## 3. Responsibilities and adoption order

| Component | Responsibility | Phase 1 treatment |
|---|---|---|
| VS Code + Git | Main workspace and source control | Required |
| Claude Code | Coding harness / terminal agent | Install only after checking account route and cost |
| FreeLLMAPI | Local unified model API, provider fallback | Evaluate first as gateway candidate |
| OmniRoute | Alternative model routing and CLI configuration | Evaluate separately; do not chain gateways initially |
| ECC-Affan | Planning, TDD, review, skills and hooks | Install one supported plugin path only |
| Ponytail | Reuse-first, minimum-change coding discipline and review commands | Install as a skill/plugin; keep full validation |
| Graphify | Read-only codebase graph and navigation | Optional; benchmark on this repository |
| Agent Skills | Selective reusable skills | Inspect individual skills; do not bulk-install |
| REA | Reverse-engineering report to traceable specification bridge | Existing integration; retain |
| Strix | Security testing | Defer until Docker, target authorization and model cost are verified |
| Playwright | Browser-level acceptance tests | Add when a web-app template is selected |
| GitHub Actions | CI evidence | Keep targeted; no blind reruns |

### Gateway rule

FreeLLMAPI and OmniRoute overlap as gateways. Do not place one in front of the other until a measured need is demonstrated. Run the same harmless model-capability probe against each independently and compare:

- actual available model IDs and provider provenance;
- whether a route is genuinely free and what quota/expiry applies;
- Anthropic Messages and/or OpenAI Chat Completions compatibility required by the selected agent;
- tool calling, streaming, context limits and structured output;
- latency, failure behaviour, rate limits and fallback semantics;
- privacy/data retention and whether requests leave the workstation;
- logs, token accounting and whether billing can be disabled or blocked.

A gateway is not itself free inference. An API-compatible endpoint may still forward to a paid provider. Unknown price or unknown billing state means BLOCK.

## 4. Windows workstation prerequisites

Record versions before installing anything:

```powershell
$PSVersionTable.PSVersion
git --version
node --version
npm --version
python --version
code --version
docker --version
```

Minimum setup:

1. Windows 11 updates and sufficient free disk space.
2. Git for Windows.
3. VS Code.
4. Python 3.11+ (the existing control-plane README specifies Python 3.11+).
5. Node.js LTS only where required by a selected CLI/plugin.
6. Docker Desktop only if an approved isolated tool needs it; do not leave it running unnecessarily.
7. WSL2 is optional, not a prerequisite. Choose native PowerShell/Git Bash or WSL2 once and document the chosen shell.

Do not paste credentials into PowerShell history, repository files, prompts, screenshots or logs.

## 5. Installation sequence

Install and verify one layer at a time. Use official project documentation and inspect installers before running them.

### 5.1 VS Code and Git

- Install VS Code and Git for Windows from their official sites.
- Open the existing `dakumitha/ai-software-factory` checkout.
- Confirm the active branch and clean working tree before edits.
- Never use the EventFlow checkout for factory experiments.

### 5.2 Claude Code

Claude Code is a coding harness, not a free model. Its normal Anthropic authentication may require an eligible paid plan or billable API access. Do not sign up for or enable billing to complete this phase.

Official Windows installation instructions: https://code.claude.com/docs

After installation, verify with:

```powershell
claude --version
claude doctor
```

Only configure it against a gateway after the compatibility and zero-spend tests below pass. Do not store API tokens in `settings.json`, project files, or Git.

### 5.3 ECC-Affan and Ponytail

Install ECC from its canonical repository only: https://github.com/affaan-m/ECC

For Claude Code, use one native plugin installation path, not a second manual installation:

```text
/plugin marketplace add https://github.com/affaan-m/ECC
/plugin install ecc@ecc
```

Install Ponytail only from https://github.com/DietrichGebert/ponytail or its official marketplace. It is a coding discipline/skill, not a coding model or agent orchestrator. Its purpose is to prefer existing code and platform capabilities, minimize unnecessary changes, and review the touched code. It must never suppress tests, validation, security checks or accessibility requirements.

Ponytail reference: https://ponytail.dev/

### 5.4 Model gateway comparison

Evaluate FreeLLMAPI and OmniRoute separately from their official sources:

- FreeLLMAPI: https://github.com/tashfeenahmed/freellmapi
- OmniRoute: https://github.com/cheaper-inference/OmniRoute

Use local-only binding initially. Do not expose a gateway dashboard or API to the public internet. Do not add real provider keys until the owner has verified the provider's price, quota, terms and privacy. Prefer a local inference route if it meets the minimum coding task.

### 5.5 Graphify and Agent Skills

- Graphify source: https://github.com/Graphify-Labs/graphify
- Agent Skills source: https://github.com/addyosmani/agent-skills

Review the exact revision, licence, scripts, hooks, MCP tools, network access and dependencies before installing. Run Graphify against a disposable/read-only checkout first. Exclude secrets, local environment files, private datasets, build outputs and generated artifacts. Add only skills that solve a demonstrated need.

### 5.6 Strix

Strix source: https://github.com/usestrix/strix

Defer installation and execution until Docker isolation, an authorized test target and a verified zero-cost inference route are available. Strix may require an LLM provider key; open-source software does not make model inference free. Never test third-party targets without authorization.

## 6. First gateway acceptance probe

Use a harmless, non-sensitive prompt. Do not send private source code or credentials.

A gateway is accepted only if all are true:

- [ ] The endpoint is local or otherwise explicitly approved.
- [ ] Provider and model identity are visible and truthful.
- [ ] The selected route is confirmed ₹0 / US$0 for the test.
- [ ] Billing fallback is disabled; quota exhaustion returns a hard stop.
- [ ] Required API protocol, streaming and tool-call behaviour work.
- [ ] Request/response logs redact keys and sensitive values.
- [ ] Token usage and rate limits are observable.
- [ ] Restarting the gateway does not lose required configuration.
- [ ] No secret is written to Git, terminal history or ordinary logs.

If no route passes, continue Phase 1 with the deterministic no-model workflow. Do not invent a free route.

## 7. First coding-agent smoke test

Use a disposable branch and a tiny documentation-only task:

1. Ask the agent to explain the repository's current project/job lifecycle.
2. Ask it to propose one documentation correction, without changing files.
3. Have it create a patch on the disposable branch.
4. Run the existing focused unit tests and repository CI checks.
5. Inspect the diff, verify no unrelated files changed, and record model/provider, token usage and elapsed time.
6. Run Ponytail review and the ECC review workflow if installed.
7. Keep the result as a pull request or local branch; do not merge or deploy automatically.

Pass criteria: the agent can read the repository, make a bounded change, explain its evidence, run the specified checks, and stop safely when a test fails or a quota is unknown.

## 8. Safety and autonomy policy

"Full autonomy" means the system may autonomously plan, code, run permitted tests, repair bounded failures, document results and prepare pull requests. The deterministic control plane remains the authority.

The following remain hard approval gates:

- paid usage, enabling billing or changing provider quotas;
- production deployment, merge to protected branches or release;
- destructive database operations or changes to production data;
- exposing services to public networks or changing DNS/domains;
- granting new permissions, secrets or external account access;
- security testing outside owned/authorized targets;
- installing/upgrading a new execution runtime or privileged tool.

Workers must use disposable least-privilege workspaces, bounded resources, command allowlists, no production secrets, patch capture, independent verification, timeouts, cancellation and resumable checkpoints. A model cannot approve its own output or declare its own tests passed.

## 9. Phase 1 evidence register

Create an evidence entry for each check with date, machine, tool/version, command, exit code, and a redacted log location.

| Check | Status |
|---|---|
| Windows / PowerShell / Git / Python / VS Code inventory | NOT RUN |
| Claude Code installed and diagnosed | NOT RUN |
| ECC installed once and skills enumerated | NOT RUN |
| Ponytail installed and review command verified | NOT RUN |
| FreeLLMAPI route and zero-spend probe | NOT RUN |
| OmniRoute route and zero-spend probe | NOT RUN |
| Gateway comparison and primary selection | NOT RUN |
| Graphify read-only repository analysis | NOT RUN |
| Agent Skills reviewed and selectively adopted | NOT RUN |
| First coding-agent smoke test | NOT RUN |
| Existing factory tests and CI evidence checked | NOT RUN |

## 10. Completion definition

Phase 1 is complete only when:

1. The developer toolchain inventory is recorded.
2. The chosen coding harness can inspect and safely edit a disposable branch.
3. At least one model route is proven to be zero-cost for the actual test, or the system is explicitly left in deterministic no-model mode.
4. ECC and Ponytail are installed without duplicate hooks/configuration, or documented as deferred.
5. The gateway decision is evidence-based; FreeLLMAPI and OmniRoute are not redundantly chained.
6. The smoke-test diff and test evidence are recorded.
7. No EventFlow files, production services, paid services or secrets were changed.

**Current reality:** this document defines the Phase 1 runbook. It does not claim that software has been installed on the owner's Windows PC or that a provider route has passed. Those machine-specific checks require running the commands on that machine.
