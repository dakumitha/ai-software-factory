# AI Software Factory

A cloud-first, repository-driven software production system designed to turn ideas into verified software through structured requirements, reusable engineering tools, agent orchestration, persistent checkpoints, automated quality gates, and controlled releases.

## Current status

**Control-plane foundation implemented; automated tests running in GitHub Actions.** The repository now contains a dependency-free Python/SQLite core for projects, durable jobs, validated state transitions, append-only job events, task dependency validation, and an HTTP JSON API. Agent execution, model-provider integration, a hosted mobile UI, sandboxed builds, and release automation are not yet implemented or verified.

## Run the current control plane

Requires Python 3.11 or newer. No Python runtime dependencies are required for the current core.

```sh
PYTHONPATH=src python -m software_factory --host 127.0.0.1 --port 8080
```

Then use:
- `GET /health` for service status
- `POST /projects` with `{"name":"Demo","idea":"Build a task tracker"}`
- `GET /projects` to list projects
- `POST /jobs` with `{"project_id":"<project-id>","tasks":[]}`
- `GET /jobs` to list jobs
- `GET /jobs/<job-id>/events` to view audit events
- `POST /jobs/<job-id>/transition` with `{"target":"NEEDS_CLARIFICATION","reason":"Need more detail"}`

The server binds to loopback by default. Remote binding is blocked unless `FACTORY_ALLOW_REMOTE=1` is explicitly set; do not expose it to the public internet without authentication, TLS, and a hardened deployment configuration. The current API is a development foundation, not a production-secure hosted service. Generated code execution is deliberately disabled.

## Design principles

1. **Reuse before rebuild:** evaluate existing projects and tools before writing replacements.
2. **Requirements before code:** every change traces to a versioned requirement and measurable acceptance criteria.
3. **Deterministic control plane:** the application, not an LLM, owns permissions, state transitions, budgets, approvals, and release decisions.
4. **Checkpoint everything important:** jobs persist inputs, decisions, outputs, logs, and resumable state.
5. **Quality gates are real:** generated code is not complete until required checks pass.
6. **Least privilege:** no secrets in prompts or logs; no arbitrary execution or production deployment without explicit policy and approval.
7. **Budget-aware by default:** free tiers are preferred, quotas are tracked, and work pauses safely when limits are reached.
8. **Portable and replaceable:** model providers, agent frameworks, storage, and deployment targets sit behind interfaces where practical.
9. **Mobile-first operations:** the owner should be able to review and control work from a phone.
10. **Honest status:** never label a build, test, deployment, or integration successful without evidence.

## Intended end-to-end flow

Idea → clarification interview → requirements and acceptance criteria → architecture and threat model → dependency-aware task graph → approved agent execution → isolated workspace → tests and security checks → human review → release → monitoring and maintenance.

## Documentation

- [Product vision and scope](docs/PRODUCT_VISION.md)
- [Architecture and trust boundaries](docs/ARCHITECTURE.md)
- [Integration register and audit rules](docs/INTEGRATION_REGISTER.md)
- [Delivery roadmap and acceptance gates](docs/ROADMAP.md)
- [Security policy](SECURITY.md)
- [Decision records](docs/decisions/README.md)
- [Test instructions](tests/README.md)

## Important constraints

- The target owner currently needs a phone-first workflow and has no budget for paid AI credits.
- Free services have quotas, sleeping limits, usage policies, and changing availability. Unlimited free compute is not assumed.
- Public repositories are untrusted inputs until reviewed for licence, maintenance, dependency, security, and compatibility.
- The existing `dakumitha/EventFlow` project is explicitly out of scope and must not be modified by this project.

## Definition of done

A capability is complete only when its requirements, implementation, tests, security implications, operating instructions, and known limitations are recorded. A production release additionally requires explicit approval and verified deployment evidence.
