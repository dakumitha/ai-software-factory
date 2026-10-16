# Reference Research: Catalogue, Agent Runtime, and Control-Room Design

**Reviewed:** 2026-10-16  
**Scope:** Research notes for the existing `feature/spec-workflow` implementation. These are design inputs, not claims of integration.

## Current repository baseline

The working branch is `feature/spec-workflow`. The open draft PR is [#1](https://github.com/dakumitha/ai-software-factory/pull/1), targeting `main`. Its head at review time was `c43a5095f2ed18ecbf19dbbbe37e6a69cb038756`. GitHub Actions reported successful runs for the repository foundation checks, core tests, and spec workflow tests on that commit.

The `--web` CLI option is present. It serves `web/connected.html` and the JSON API from one origin, with SQLite-backed project persistence. The older `web/index.html` is a browser-local mockup and is not the connected UI. The current API is unauthenticated and intended for loopback-only development. No remote agent, secure hosted control room, or isolated execution worker is connected.

The execution environment used for this review could not clone the repository over the network, so local tests and an independent working-tree check were not possible. The CI result above is GitHub-reported evidence, not a claim that tests were run locally.

## OpenAlternative: product pattern to learn from

- Main catalogue: https://openalternative.co/
- About: https://openalternative.co/about
- Categories: https://openalternative.co/categories

OpenAlternative describes itself as a community-driven directory of open-source alternatives to proprietary software. Its category pages group tools into understandable product areas, including AI, developer tools, infrastructure, productivity, security, analytics, and business software.

### Apply the pattern, not the branding

Build a searchable, structured directory inside the factory for **tools that may help build software**, rather than a general clone of OpenAlternative. Candidate groups:

- Coding agents and agent SDKs
- Models and inference providers
- Workflow/orchestration frameworks
- Sandboxes and remote execution
- Git hosting, CI, build and test tools
- Databases, artifact storage and deployment
- Design systems, icon libraries and accessibility tools

Each entry should contain a stable ID, name, category, tags, official project URL, source repository, licence evidence, maintenance evidence, model/runtime prerequisites, data-handling notes, supported integration mode, pricing classification, quota notes, date checked, evidence URLs, verification state, and human approval state.

Keep the existing SQLite API Discovery Registry as the initial persistence/review boundary. Its current importer and approval process are a useful foundation, but they do not automatically verify a provider, fetch a live catalogue, invoke an integration, or certify safety. Do not load executable plugins directly from catalogue records. The catalogue should be metadata, not code execution.

### Pricing labels must be honest

- **Free/open-source software:** the software can be used under its licence, but compute, models, hosting, storage, bandwidth, or operations may still cost money.
- **Free service tier:** no charge within stated limits; record quotas, eligibility, expiry/change risk and billing settings.
- **Freemium:** a free subset exists, but higher usage or features cost money.
- **Paid:** a paid plan is required for the intended use.
- **Unknown / needs review:** do not treat as a zero-cost option.

Never infer “free compute” from an open-source licence. If a price, quota, billing state, licence, or provider term cannot be confirmed, mark it unknown and block automatic use where it could create a charge.

## Agent runtime evaluation

### OpenHands Software Agent SDK

- Repository: https://github.com/OpenHands/software-agent-sdk
- Documentation: https://docs.openhands.dev/sdk
- Introduction: https://www.openhands.dev/blog/introducing-the-openhands-software-agent-sdk

The repository README describes Python, TypeScript and REST APIs for coding agents, and supports local workspaces or ephemeral workspaces through an Agent Server, for example using Docker or Kubernetes. The repository advertises an MIT licence. This makes it a credible **candidate adapter**, not a reason to replace the existing control plane.

Important distinction: an SDK, Agent Server, or ephemeral workspace is not automatically free or a security sandbox. Model inference and hosting may have separate costs. A production integration still needs a pinned version, dependency/licence review, a proven no-cost model route, strict workspace/network/resource boundaries, timeouts, cancellation, output caps, audit evidence and crash recovery tests.

**Decision:** do not add it as a mandatory dependency yet. First define and test a narrow worker contract with a deterministic fake worker. Integrate OpenHands only when the free model path and isolation gates are demonstrated.

### GitHub Actions as a bounded cloud worker

GitHub documents standard GitHub-hosted runner use as free for public repositories. See https://docs.github.com/en/actions/concepts/billing-and-usage and https://docs.github.com/en/billing/concepts/product-billing/github-actions.

This can provide limited, event-driven remote execution for public-repository tasks, subject to GitHub's current policies and available runner types. It is not a persistent interactive cloud computer, does not provide free model inference, and should not be described as unlimited compute. Avoid large matrices and blind reruns; use targeted tests, timeouts, concurrency controls and explicit cost safeguards.

## Design-reference investigation

These sites are inspiration sources. Do not copy their branding, code, screenshots or proprietary assets. Record the specific interaction pattern we want and implement an original accessible design.

| Reference | Resolved URL | Useful pattern | Caution |
|---|---|---|---|
| Scrolltide | https://www.scrolltide.co/ | Scroll storytelling, section templates, visual components and UI examples | Its catalogue includes paid offerings; do not assume assets are free to reuse |
| Navbar Gallery | https://www.navbar.gallery/ | Navigation patterns: static/sticky headers, dropdowns, mega menus, sidebars, search, announcements and breadcrumbs | Treat screenshots as reference, not reusable source assets |
| Footer Design | https://www.footer.design/ | Footer patterns organised by visual type and style | Recreate patterns in our own visual identity |
| CTA Gallery | https://www.cta.gallery/ | Call-to-action patterns for forms, downloads, pricing, signup and navigation | Use clear, truthful calls to action, not manipulative conversion tricks |
| Referral style | https://webflow.com/made-in-webflow/referral and https://webflow.com/made-in-webflow/referrals | Invitation/referral flow examples and community implementations | No referral system is needed for the first vertical slice |
| “Superhero” | https://webflow.com/made-in-webflow/superhero and https://dribbble.com/search/superhero-website | Search results suggest superhero-themed site examples, not one unambiguous product | Original reference remains ambiguous; confirm if a specific Superhero site was intended |
| 3D Icons | https://3dicons.co/ and https://github.com/realvjy/3Dicons | Lightweight illustrative 3D icon direction; the repository identifies CC0-1.0 | Verify the exact asset/version licence before including files in the product |

### Original design direction

Use a distinctive engineering workbench aesthetic: calm dark-neutral surfaces, one restrained mint accent, clear status colours, legible typography, compact information density, and subtle motion only where it helps users understand state. The existing connected UI already has a responsive foundation; improve it incrementally rather than replacing it with a flashy landing page.

- Mobile-first bottom navigation on phones and clear persistent navigation on desktop.
- Strong project/task hierarchy, real status labels, empty states and visible failure states.
- Accessible contrast, keyboard focus, semantic landmarks, reduced-motion support and comfortable touch targets.
- Keep 3D imagery decorative and optional; never let it slow down task monitoring or obscure evidence.
- Make the agent status, spend ceiling, provider quota and approval requirements visible.
- No pretend activity, fake provider connections, or sample data presented as real runs.

## Recommended next vertical slice

1. Keep the deterministic control plane as the authority.
2. Add a small, versioned, metadata-only provider catalogue with search/category filters and evidence-backed pricing/licence states.
3. Add a deterministic fake worker implementing a narrow worker interface; persist its task attempt, bounded output, result and verification evidence.
4. Surface actual project/spec/task status and evidence in the connected UI.
5. Add an OpenHands adapter only after the runtime, free inference path and isolation gates are proven.
6. Do not expose the unauthenticated development API publicly. Secure authentication and authorization must precede hosted cross-device access.

## Sources checked

- OpenAlternative: https://openalternative.co/about and https://openalternative.co/categories
- OpenHands SDK: https://github.com/OpenHands/software-agent-sdk
- GitHub Actions usage: https://docs.github.com/en/actions/concepts/billing-and-usage
- Scrolltide: https://www.scrolltide.co/
- Navbar Gallery: https://www.navbar.gallery/
- Footer Design: https://www.footer.design/
- CTA Gallery: https://www.cta.gallery/
- Webflow referral and superhero galleries: linked in the table above
- 3Dicons: https://3dicons.co/ and https://github.com/realvjy/3Dicons
