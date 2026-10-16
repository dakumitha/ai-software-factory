# Security Policy

## Scope

This policy applies to the AI Software Factory repository and future execution platform. It does not authorise changes to other repositories.

## Safe development rules

- Treat prompts, public repositories, packages, generated code, and agent commands as untrusted.
- Review source and licences before running third-party code.
- Do not commit credentials, tokens, private keys, production data, or secrets in examples.
- Use least-privilege credentials and short-lived tokens where supported.
- Run generated code in an isolated workspace with bounded CPU, memory, time, filesystem, and network access where the host permits.
- Keep control-plane credentials out of coding-agent environments.
- Require explicit approval for repository writes, privileged integrations, and production deployments.
- Keep audit records for approvals, external actions, releases, and failures.
- Never claim security scanning passed unless a recorded run produced that result.
- Pause safely when quota, budget, or safety limits are reached.

## Reporting

Do not publish exploitable details of a real vulnerability in an issue. Until a dedicated private reporting channel is configured, contact the repository owner through a private channel and include affected version/commit, impact, reproduction details, and suggested mitigation.

## Current limitation

These are policy commitments, not proof that enforcement mechanisms are already implemented. Implementation and tests are required before the platform may claim these controls are operational.
