# AI Software Factory

A cloud-first, repository-driven software production system designed to turn ideas into verified software through structured requirements, reusable engineering tools, agent orchestration, persistent checkpoints, automated quality gates, and controlled releases.

## Current status

**Control-plane foundation implemented; automated tests running in GitHub Actions.** The repository now contains a dependency-free Python/SQLite core for projects, durable jobs, validated state transitions, append-only job events, task dependency validation, and an HTTP JSON API. Agent execution, model-provider integration, a hosted mobile UI, sandboxed builds, and release automation are not yet implemented or verified.

## Phone + desktop control room

A responsive, API-connected local control room is available through the `--web` launch option. It reads and creates projects through the existing SQLite-backed API, so records persist across browser sessions on that server. This is still a development prototype: it has no authentication, remote worker, hosted deployment, or safe public cross-device access. The standalone [`web/index.html`](web/index.html) remains the local-storage-only mockup. See [Phone + Compute Control Room](docs/PHONE_COMPUTE_CONTROL_ROOM.md) for architecture and limits.

## Run the current control plane

Requires Python 3.11 or newer. No Python runtime dependencies are required for the current core.

```sh
PYTHONPATH=src python -m software_factory --host 127.0.0.1 --port 8080
```

To open the connected control room and API on the same local origin, run:

```sh
PYTHONPATH=src python -m software_factory --web --host 127.0.0.1 --port 8080
```

Open `http://127.0.0.1:8080/`. The connected UI uses the server API; it does not silently fall back to browser-only storage.

Then use:
- `GET /health` for service status
- `POST /projects` with `{"name":"Demo","idea":"Build a task tracker"}`
- `GET /projects` to list projects
- `POST /jobs` with `{"project_id":"<project-id>","tasks":[]}`
- `GET /jobs` to list jobs
- `GET /jobs/<job-id>/events` to view audit events
- `POST /jobs/<job-id>/transition` with `{"target":"NEEDS_CLARIFICATION","reason":"Need more detail"}`

The server binds to loopback by default. Remote binding is blocked unless `FACTORY_ALLOW_REMOTE=1` is explicitly set; do not expose it to the public internet without authentication, TLS, and a hardened deployment configuration. The current API is a development foundation, not a production-secure hosted service. Generated code execution is deliberately disabled.

## Deterministic dry-run demo

Run the factory's orchestration flow without paid services, network calls, an AI provider, or shell execution:

```sh
PYTHONPATH=src python -m software_factory --demo
```

The demo uses a disposable temporary database and reports the specification approval, generated task plan, worker lease, task attempts, and final review state. It is an orchestration demonstration only: it does not generate source code or run the acceptance tests. See [Deterministic Demo](docs/DETERMINISTIC_DEMO.md).

Run the focused regression tests with:

```sh
PYTHONPATH=src python -m unittest discover -s tests -p 'test_demo.py' -v
```

## API Discovery Registry

The SQLite-backed API Discovery Registry is also exposed through the local JSON API. It supports candidate creation, filtering, review, approval/rejection, and audit history without invoking third-party services. For CLI use:

    PYTHONPATH=src python -m software_factory.api_registry add --name "Example API" --category developer-tools --source-url "https://github.com/example/catalogue"
    PYTHONPATH=src python -m software_factory.api_registry list --status PENDING

See [API Discovery Registry guide](docs/API_DISCOVERY_REGISTRY.md) for the review gate and limitations.

## Read-only worker CLI

Inspect persisted job state without opening SQLite manually. These commands do not execute tasks or print task payloads:

```sh
PYTHONPATH=src python -m software_factory.worker_cli --database data/factory.sqlite3 list
PYTHONPATH=src python -m software_factory.worker_cli --database data/factory.sqlite3 status <job-id>
```

See [Read-only Worker CLI](docs/WORKER_CLI.md) for filters, output fields, exit codes, and privacy boundaries.

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

## Multi-product strategy

The factory is intended to support multiple product families, including publishing/newsletters, commerce marketplaces, travel/accommodation marketplaces and business applications. The strategy defines the shared engineering lifecycle, reusable capability library, template contract, security/reliability gates and staged delivery plan. These are long-term goals, not claims that these products already exist.

See [Multi-Product Software Factory Strategy](docs/PRODUCT_FAMILY_STRATEGY.md).

## Documentation

- [Product vision and scope](docs/PRODUCT_VISION.md)
- [Architecture and trust boundaries](docs/ARCHITECTURE.md)
- [API Discovery Registry](docs/API_DISCOVERY_REGISTRY.md)
- [Read-only Worker CLI](docs/WORKER_CLI.md)
- [Integration register and audit rules](docs/INTEGRATION_REGISTER.md)
- [External repository integration guide](docs/EXTERNAL_REPOSITORY_INTEGRATION_GUIDE.md)
- [Machine-readable repository integration manifest](config/integrations/repositories.json)
- [Delivery roadmap and acceptance gates](docs/ROADMAP.md)
- [Deterministic control-plane demo](docs/DETERMINISTIC_DEMO.md)
- [Multi-product strategy](docs/PRODUCT_FAMILY_STRATEGY.md)
- [Free-first agent engine integration plan](docs/FREE_FIRST_AGENT_ENGINE.md)
- [Reference research and design direction](docs/REFERENCE_RESEARCH.md)
- [Phone + compute control room](docs/PHONE_COMPUTE_CONTROL_ROOM.md)
- [Security policy](SECURITY.md)
- [Decision records](docs/decisions/README.md)
- [Documentation standard and change workflow](docs/DOCUMENTATION_STANDARD.md)
- [Development log](docs/DEVELOPMENT_LOG.md)
- [Test instructions](tests/README.md)

## Important constraints

- The target owner currently needs a phone-first workflow and has no budget for paid AI credits.
- Free services have quotas, sleeping limits, usage policies, and changing availability. Unlimited free compute is not assumed.
- Public repositories are untrusted inputs until reviewed for licence, maintenance, dependency, security, and compatibility.
- The existing `dakumitha/EventFlow` project is explicitly out of scope and must not be modified by this project.

## Definition of done

A capability is complete only when its requirements, implementation, tests, security implications, operating instructions, and known limitations are recorded. A production release additionally requires explicit approval and verified deployment evidence.
