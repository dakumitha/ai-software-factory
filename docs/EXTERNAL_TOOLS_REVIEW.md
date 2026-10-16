# External tool review (2026-10-16)

- Poe: optional model/interface candidate only. API access, quotas, terms, and cost must be verified; do not assume free unlimited inference.
- Wron.ai: app-generation accelerator candidate, not an engine dependency. Free usage, API availability, and source export were not verified.
- Learn Anything: reference for knowledge maps and learning paths. Audit the exact repository's licence, dependencies, and maintenance before reusing code.
- VoiceStudio: defer as an optional audio plugin. It is not a coding engine or cloud compute. Review AGPL-3.0 and model-asset terms before embedding the NeoTheCode repository.
- GitHub Spec Kit: MIT-licensed spec/plan/task workflow candidate. Compare with the existing spec workflow on one feature before adopting; avoid duplicate processes.

None of these candidates has been integrated or verified end-to-end. Priority: fix and verify the plan API, then implement one quota-aware, isolated agent/execution adapter. A free signup or trial does not imply unlimited compute.
