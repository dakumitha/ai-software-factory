# Phone + Compute Control Room

## Product requirement

The owner must be able to use the same software factory from both a phone and a desktop browser. The phone is a full control surface for project intake, task review, approvals, run monitoring and evidence inspection. Heavy builds and agent execution happen on a separate remote worker, not on the phone.

## Current implementation

`web/index.html` is the original browser-local UI mockup. A second page, `web/connected.html`, is served with the existing API by `PYTHONPATH=src python -m software_factory --web --host 127.0.0.1 --port 8080`:
- Responsive on phone and desktop.
- Loads project records from `GET /projects` and creates them through `POST /projects`.
- Stores those records in the factory's SQLite database, not browser local storage.
- Reports API connection errors instead of silently saving to local storage.
- Displays the ₹0 spend target and clearly states that no remote worker or agent is connected.
- Uses the same origin for the UI and API, avoiding browser CORS configuration for this local mode.

This is a local development connection, not a hosted or production-safe multi-device service. The API remains bound to loopback by default. The UI is not authenticated, and setting `FACTORY_ALLOW_REMOTE=1` is not a substitute for authentication, TLS, authorization and hardened hosting. Do not expose this server publicly.

## Target architecture

```text
Phone browser / Desktop browser
             |
             | HTTPS, authenticated session
             v
Control-room web app
             |
             v
Factory API and durable database
             |
             +--> Specification / task graph / approval policy
             |
             +--> Budget and provider policy
             |
             v
Job queue / durable dispatcher
             |
             v
Isolated remote worker (disposable workspace)
             |
             +--> Code diff and artifacts
             +--> Tests, build and security evidence
             +--> Usage / cost / quota record
             |
             v
Factory API -> phone and desktop status updates
```

## Important design decisions

- **Responsive, not phone-only:** the same app must work on a phone and desktop, with no desktop-only essential action.
- **Compute is separate:** the UI does not build code or host an LLM.
- **Shared state:** production use requires authenticated server-side persistence. Local storage is only for this prototype.
- **Secure by default:** do not expose the existing development HTTP API to the public internet. Require authentication, TLS, server-side authorization, CSRF protection where applicable, rate limits, audit events and secure secret storage.
- **Worker isolation:** generated code is untrusted. Workers need disposable workspaces, least privilege, no production secrets by default, network policy, resource/time/output limits and independent verification.
- **Zero-spend default:** do not enable a paid model, VM, database, hosted agent or deployment provider without explicit approval. If free quota is unavailable or unknown, pause.
- **Honest status:** only a backend-confirmed worker can mark a job as running or completed. Evidence links to actual logs, artifacts, test results and commit/diff identifiers.
- **No fake multi-device sync:** browser storage is device-local. Server persistence and authentication are required for phone-to-desktop continuity.

## Hosting notes

The prototype can be previewed as a static file, but this repository's eventual goal is a software-production control plane, not a static marketing site. GitHub Pages has restrictions against use as free hosting for a site primarily serving a commercial SaaS; do not use it as the permanent host for the production control room. Check current provider terms and quotas before choosing a host.

## Acceptance criteria for a real connected platform

1. Open the same account from phone and desktop and see the same projects and job status.
2. Create a project from either device and persist it on the server.
3. Submit an approved bounded task to a remote worker without using phone CPU for builds.
4. Follow queued/running/paused/failed/completed status from either device.
5. Inspect actual diff, logs, artifacts, tests and security checks.
6. Pause on unknown costs or exhausted free quota, with no paid fallback.
7. Require explicit approval for consequential execution, merge, deployment and spend.
8. Recover after browser closure or worker restart without silently replaying uncertain side effects.
9. Pass authentication, authorization, isolation and dependency/licence review before public use.
10. Verify all claims with tests and a real end-to-end run.

## Next implementation order

1. Add authentication and authorization before any hosted access; current API endpoints are development-only.
2. Add job status/event polling and actual evidence links to the connected UI.
3. Establish a secure, persistent hosted database and deployment path without enabling paid services by default.
4. Add an isolated remote worker adapter, initially using a no-cost bounded CI job where appropriate.
5. Evaluate OpenHands SDK as an optional agent worker only after model access, workspace isolation, licence and quota checks.
6. Add end-to-end tests proving two devices see the same server-side project data, plus security and recovery tests.

Do not claim the platform is cloud-connected until steps 1-4 have been demonstrated in a real run.
