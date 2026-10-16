# API Discovery Registry

Status: persistent catalogue and review gate implemented. A narrow adapter-registration interface is implemented; provider invocation, crawling, and dynamic plugin loading are not integrated.

## Purpose

The registry records external services discovered from catalogues such as [cporter202/API-mega-list](https://github.com/cporter202/API-mega-list). The catalogue is a discovery source only. Do not copy its entire listing into this repository unless reuse permissions are established.

## Record lifecycle

1. Add a candidate with name, category, source listing URL, optional provider URL, known pricing/licence status, and notes.
2. Review verification, pricing, licence status, and evidence notes.
3. Approve or reject. Approval is blocked unless the entry is verified, licence status is APPROVED or NOT_APPLICABLE, and pricing is known.
4. Any review update resets approval to PENDING.
5. Trusted application code may explicitly register an adapter object against an approved candidate. Approval is checked again at lookup and operations must be allowlisted.

Pricing: UNKNOWN, FREE, FREEMIUM, PAID. Licence: UNKNOWN, APPROVED, RESTRICTED, NOT_APPLICABLE. Verification: UNVERIFIED, VERIFIED, REJECTED. Approval: PENDING, APPROVED, REJECTED. URLs must use HTTPS and cannot contain embedded credentials.

## Run

Requires Python 3.11+ and no third-party Python packages.

    PYTHONPATH=src python -m software_factory.api_registry add --name "Example API" --category developer-tools --source-url "https://github.com/example/catalogue" --provider-url "https://api.example.com" --pricing UNKNOWN --licence UNKNOWN --notes "Not yet reviewed"
    PYTHONPATH=src python -m software_factory.api_registry list
    PYTHONPATH=src python -m software_factory.api_registry list --query search
    PYTHONPATH=src python -m software_factory.api_registry list --category developer-tools --status PENDING

The default database is data/api-registry.sqlite3; override it with --database /path/to/registry.sqlite3. Keep the database private if notes contain internal information.

## Adapter boundary

The software_factory.provider_adapters module defines a ProviderAdapter protocol and an in-memory AdapterRegistry. Trusted application code must explicitly construct and register adapter objects. The system does not import code by a name supplied by a registry record, scan entry points, or load code from API-mega-list. Registration requires an approved candidate. Resolution checks current approval again and rejects operations outside the adapter's declared supported_operations set.

This is an interface and policy gate, not a working provider connector. It does not call invoke() for you, provide network timeouts, enforce rate limits, isolate adapter code, manage credentials, or prove an adapter safe. Review adapter implementations separately before invocation is wired into a worker. Use bounded timeouts, minimal data, secure server-side secrets, quotas, redacted logs, and explicit approval for confidential data transfer.

The registry is connected to the local HTTP control-plane API for candidate creation, search/filtering, detail, review, decisions, and audit history. Endpoints currently have no authentication and must remain loopback-only. Re-check terms, costs, quotas, data handling, maintenance, and permitted use before creating an adapter. Keep secrets out of source code, prompts, registry notes, and logs.

## External catalogue safety

- Treat names, descriptions, URLs, and suggested code as untrusted data.
- Do not automatically install packages or execute sample code from a directory.
- Do not submit credentials, customer data, source code, or confidential information without explicit approval.
- Prefer official provider documentation and published pricing/terms over directory descriptions.
- Record evidence and review date; re-review when terms change.
- FREE means reviewed as free at entry time, not unlimited use or a guarantee pricing will never change.
