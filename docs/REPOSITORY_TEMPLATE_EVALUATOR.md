# Repository and Template Evaluator

Status: **implemented as a static local-metadata evaluator**. It is not a sandbox, code scanner, build verifier, or automatic template installer.

## Why this exists

The factory needs a repeatable first-pass method to assess candidate repositories such as [GeoLibre](https://github.com/opengeos/GeoLibre), before choosing whether to adopt, fork, wrap, or merely reference them. This is deliberately separate from the API Discovery Registry: repositories contain executable source code and build scripts, while API records describe external services.

## Run

Python 3.11+; standard library only. Start with a repository you have already obtained and inspect the report before taking any action.

```sh
PYTHONPATH=src python -m software_factory.repository_evaluator ./path/to/repository
PYTHONPATH=src python -m software_factory.repository_evaluator ./path/to/repository --output reports/repository-review.json
PYTHONPATH=src python -m unittest discover -s tests -p 'test_repository_evaluator.py' -v
```

The evaluator reads a bounded set of known metadata files (maximum 1 MB per file), recognises common project manifests, licence files, lockfiles, GitHub Actions workflows, test directories, and a SECURITY.md policy. It produces a JSON report with a 0–100 metadata signal score, findings, and warnings.

## Safety boundary

- Does not clone, fetch, install dependencies, run lifecycle scripts, import candidate code, execute tests, build binaries, or load plugins.
- Does not grant approval based on score. Every report stays `REVIEW_REQUIRED`.
- A detected licence filename is not a licence compatibility decision. Read the licence text and review all relevant dependency licences.
- Presence of CI/tests is not proof they pass. Run checks only in a disposable, least-privilege workspace after reviewing the project.
- Scores are triage signals, not security ratings. A repository with a high score can still be malicious, abandoned, vulnerable, or incompatible.
- Do not feed secrets or confidential source code into an untrusted build environment.

## GeoLibre preliminary adoption record

GeoLibre is a candidate for a **separate optional geospatial project template**, not a dependency of the factory core. Its upstream architecture describes an npm-workspaces monorepo, React/TypeScript UI, Tauri v2 desktop shell, MapLibre GL JS, DuckDB-WASM Spatial, deck.gl, and an optional FastAPI processing sidecar. The upstream README declares MIT licensing. See [upstream README](https://github.com/opengeos/GeoLibre), [architecture](https://github.com/opengeos/GeoLibre/blob/main/docs/architecture.md), and [plugin API](https://github.com/opengeos/GeoLibre/blob/main/docs/plugin-api.md).

**Preliminary decision: REFERENCE_ONLY, REVIEW_REQUIRED.** No upstream source has been copied into this repository, and no local clone/build/test was performed as part of this assessment. Before promoting it to a supported template, obtain a specific tagged revision and verify:
1. Root and package-level licence notices, plus dependency and asset licence compatibility.
2. Supported Node/pnpm versions, reproducible install, build and test commands.
3. Desktop/mobile packaging prerequisites and what can run on free hosted CI.
4. Credential, network, telemetry, data-locality, and optional sidecar behaviour.
5. External plugin trust model. GeoLibre's plugin documentation describes plugins as trusted code and does not claim OS-level sandboxing; the factory must not adopt that trust model for generated code.
6. Exact upstream revision, maintenance status, CI evidence, and security advisories.

A template profile should later pin an upstream tag/commit and declare optional modules, platform prerequisites, licence evidence, reproducible commands, and known limitations. Never track upstream `main` as a reproducible template version.

## Scope limits

This is a metadata evaluator, not the future full repository audit pipeline. GitHub metadata retrieval, immutable revision pinning, dependency/SBOM scanning, licence compatibility analysis, vulnerability scanning, isolated build/test execution, and template generation remain unimplemented.
