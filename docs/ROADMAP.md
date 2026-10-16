# Accelerated Delivery Roadmap

**Target:** demonstrate a useful end-to-end engine slice as quickly as free resources allow. This is a target, not a guarantee of a universal autonomous factory.

## Phase 0: Foundation and control plane
- [x] SQLite project/job persistence, lifecycle validation, event history, task graph validation, and JSON HTTP API.
- [x] Versioned specs, acceptance criteria, and approval-gated deterministic planning.
- [x] Durable checkpoints, worker leases, task-attempt records, and interrupted-job inventory.
- [x] API discovery registry, review lifecycle, explicit adapter interface, and preview-first local catalogue import.
- [x] Static local repository metadata evaluator.
- [x] Deterministic allowlisted execution controller for one task at a time.
- [ ] Independent verification evidence and safe artifact workspace.
- [ ] Authentication for any non-local access.

## Phase 1: Demonstrated end-to-end vertical slice
- [ ] Connect approved specification → task plan → explicit approval → bounded worker execution → independent verification → reviewable artifact.
- [ ] Add a safe artifact writer and tests for path traversal, size limits, and recovery.
- [ ] Add controller CLI commands for one-step execution and status inspection.
- [ ] Demonstrate a small deterministic example without external model/API costs.

## Phase 2: Agent integration
- [ ] Choose a coding agent and model route after verifying terms, real free quotas, data flow, and persistence.
- [ ] Use a disposable least-privilege workspace and explicit command allowlist.
- [ ] Store diffs, test logs, verification evidence, and budget events.
- [ ] Pause safely on quota exhaustion; never silently incur paid usage.

## Phase 3: Control room and delivery
- [ ] Phone-friendly project/task/status UI.
- [ ] Authentication, permissions, deployment and rollback controls.
- [ ] Additional language/framework templates based on reproducible evidence.

## Safety and CI budget
- Keep generated code and repository plugins untrusted.
- Never execute task titles, prompts, or generated code as shell commands.
- Never disable tests or quality gates to make CI green.
- Prefer targeted checks and do not blindly rerun workflows.
