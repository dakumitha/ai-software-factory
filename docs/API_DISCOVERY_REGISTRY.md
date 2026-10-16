# API Discovery Registry

Status: first implementation slice. This is a persistent catalogue and review gate, not an automatic API crawler or runtime integration system.

## Purpose

The registry gives the Software Factory a controlled place to record external services discovered from catalogues such as [cporter202/API-mega-list](https://github.com/cporter202/API-mega-list). The catalogue is a discovery source only. Do not copy its entire listing into this repository unless reuse permissions are established.

## Record lifecycle

1. Add a candidate with name, category, source listing URL, optional provider URL, known pricing/licence status, and notes.
2. Review the verification, pricing, licence status, and evidence notes.
3. Decide whether to approve or reject. Approval is blocked unless the entry is verified, licence status is APPROVED or NOT_APPLICABLE, and pricing is known.
4. Any review update resets approval to PENDING.

Pricing values: UNKNOWN, FREE, FREEMIUM, PAID. Licence values: UNKNOWN, APPROVED, RESTRICTED, NOT_APPLICABLE. Verification values: UNVERIFIED, VERIFIED, REJECTED. Approval values: PENDING, APPROVED, REJECTED.

URLs must use HTTPS and may not contain embedded credentials. The registry does not visit URLs, call provider APIs, install packages, execute code, or handle credentials.

## Run

Requires Python 3.11+ and no third-party Python packages.

    PYTHONPATH=src python -m software_factory.api_registry add --name "Example API" --category developer-tools --source-url "https://github.com/example/catalogue" --provider-url "https://api.example.com" --pricing UNKNOWN --licence UNKNOWN --notes "Not yet reviewed"
    PYTHONPATH=src python -m software_factory.api_registry list
    PYTHONPATH=src python -m software_factory.api_registry list --query search
    PYTHONPATH=src python -m software_factory.api_registry list --category developer-tools --status PENDING

The default database is data/api-registry.sqlite3; override it with --database /path/to/registry.sqlite3. Keep the database in private, backed-up storage if notes contain internal information.

## Python review interface

The first slice exposes a Python interface for review/approval:

    from software_factory.api_registry import ApiRegistry
    registry = ApiRegistry("data/api-registry.sqlite3")
    candidate = registry.add("Example API", "developer-tools", "https://github.com/example/catalogue", pricing_status="FREEMIUM")
    registry.review(candidate["id"], verification_status="VERIFIED", licence_status="APPROVED", pricing_status="FREEMIUM", notes="Official documentation reviewed")
    registry.decide(candidate["id"], "APPROVED", reason="Approved for adapter prototype")

The registry is now connected to the local HTTP control-plane API for candidate creation, search/filtering, detail, review, decisions, and audit history. Registry mutations are recorded in a dedicated SQLite audit stream in the same database configured for the control plane. It is not connected to the agent planner, model router, package manager, or execution environment. Approval is metadata, not proof that a provider is secure or appropriate for every use. The HTTP endpoints currently have no authentication and must remain loopback-only. Re-check terms, costs, quotas, data handling, maintenance, and permitted use before creating an adapter. Keep provider secrets out of source code, prompts, registry notes, and logs.

## External catalogue safety

- Treat names, descriptions, URLs, and suggested code as untrusted data.
- Do not automatically install packages or execute sample code from a directory.
- Do not submit credentials, customer data, source code, or confidential information to a provider without explicit approval.
- Prefer official provider documentation and published pricing/terms over directory descriptions.
- Record evidence and review date; re-review when provider terms change.
- FREE means reviewed as free at the time of entry, not unlimited use or a guarantee that pricing will never change.
