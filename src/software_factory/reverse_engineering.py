"""Reverse-engineering analysis bridge and specification generator.

Integrates insights from REA (Reverse Engineer Anything, github.com/morluto/rea)
and design system extractions (e.g. Figma layouts, Lovable component flows)
into traceable, validated AI Software Factory specifications.

Enforces trust boundary:
- Decompiled logic and extracted schemas are treated as untrusted inputs.
- Extracted features are converted into formal requirements with acceptance criteria.
- Inferred logic and uncertainties become explicit assumptions and open questions.
- Resulting specifications strictly pass `_validate_spec` in `software_factory.specs`.
"""
from __future__ import annotations

import json
import re
from typing import Any, Mapping

from .core import ValidationError
from .specs import _validate_spec


def _slugify(text: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "-", text.strip().upper()).strip("-")
    return slug[:24] or "FEATURE"


def parse_rea_analysis_report(report_data: dict[str, Any] | str) -> dict[str, Any]:
    """Parse and normalize an analysis report from REA or UI reverse-engineering."""
    if isinstance(report_data, str):
        try:
            parsed = json.loads(report_data)
        except json.JSONDecodeError as exc:
            raise ValidationError(f"Invalid JSON in analysis report: {exc}") from exc
    elif isinstance(report_data, Mapping):
        parsed = dict(report_data)
    else:
        raise ValidationError("Analysis report must be a JSON string or mapping.")

    normalized = {
        "target_name": str(parsed.get("target_name", "Analyzed Application")).strip(),
        "evidence": parsed.get("evidence", []),
        "inferred_logic": parsed.get("inferred_logic", []),
        "components": parsed.get("components", []),
        "api_contracts": parsed.get("api_contracts", []),
        "unknowns": parsed.get("unknowns", []),
        "limitations": parsed.get("limitations", []),
    }

    if not isinstance(normalized["components"], list):
        raise ValidationError("Report components must be a list.")
    if not isinstance(normalized["unknowns"], list):
        raise ValidationError("Report unknowns must be a list.")

    return normalized


def convert_rea_report_to_specification(
    report_data: dict[str, Any] | str,
    title: str,
    goal: str,
    *,
    platform: str = "web",
) -> dict[str, Any]:
    """Convert reverse-engineered analysis report into a valid Factory specification.

    Converts:
    - Extracted components/features -> Traceable Requirements with Acceptance Criteria.
    - Inferred logic -> Explicit Assumptions.
    - Reverse-engineering limitations -> Constraints.
    - Surfaced unknowns -> Open Questions (which must be resolved before approval).
    """
    report = parse_rea_analysis_report(report_data)

    target_title = title.strip() or f"{report['target_name']} Architecture Spec"
    target_goal = goal.strip() or f"Implement verifiable software inspired by {report['target_name']} analysis."

    requirements = []
    seen_ids: set[str] = set()

    # 1. Map components and UI structures to requirements
    components = report["components"]
    if not components:
        # Fallback requirement if no explicit components listed
        req_id = "REQ-CORE-001"
        requirements.append({
            "id": req_id,
            "description": f"Implement core functionality for {report['target_name']}",
            "priority": "must",
            "acceptance_criteria": [
                f"Application initializes and renders core layout on {platform}.",
                "Baseline state management handles primary user interactions.",
            ],
        })
    else:
        for idx, comp in enumerate(components, start=1):
            name = comp.get("name") if isinstance(comp, dict) else str(comp)
            slug = _slugify(name)
            req_id = f"REQ-UI-{slug}"
            if req_id in seen_ids:
                req_id = f"REQ-UI-{slug}-{idx}"
            seen_ids.add(req_id)

            desc = (
                comp.get("description", f"Implement {name} UI component and layout")
                if isinstance(comp, dict)
                else f"Implement {name} UI component"
            )

            criteria = []
            if isinstance(comp, dict) and comp.get("acceptance_criteria"):
                criteria = [str(c).strip() for c in comp["acceptance_criteria"] if str(c).strip()]
            if not criteria:
                criteria = [
                    f"{name} renders with responsive layout according to design tokens.",
                    f"{name} handles input events and updates state immutably.",
                ]

            priority = "must" if idx <= 3 else "should"
            if isinstance(comp, dict) and comp.get("priority") in {"must", "should", "could", "wont"}:
                priority = comp["priority"]

            requirements.append({
                "id": req_id,
                "description": desc,
                "priority": priority,
                "acceptance_criteria": criteria,
            })

    # 2. Map API contracts to requirements
    for idx, api in enumerate(report.get("api_contracts", []), start=1):
        endpoint = api.get("endpoint", f"endpoint-{idx}") if isinstance(api, dict) else str(api)
        slug = _slugify(endpoint)
        req_id = f"REQ-API-{slug}"
        if req_id in seen_ids:
            req_id = f"REQ-API-{slug}-{idx}"
        seen_ids.add(req_id)

        desc = (
            api.get("description", f"Implement API contract for {endpoint}")
            if isinstance(api, dict)
            else f"Implement endpoint {endpoint}"
        )
        method = api.get("method", "POST") if isinstance(api, dict) else "POST"

        requirements.append({
            "id": req_id,
            "description": desc,
            "priority": "must",
            "acceptance_criteria": [
                f"{method} {endpoint} validates input payload schema.",
                f"{method} {endpoint} returns structured JSON response with error handling.",
            ],
        })

    # 3. Inferred logic becomes explicit assumptions
    assumptions = [
        f"Design and architecture derived from reverse engineering analysis of {report['target_name']}.",
        "Implementation uses clean-room implementation without copying proprietary binary code.",
    ]
    for inf in report.get("inferred_logic", []):
        text = inf if isinstance(inf, str) else json.dumps(inf)
        if text.strip():
            assumptions.append(f"Inferred behavior: {text.strip()}")

    # 4. Limitations become explicit constraints
    constraints = [
        "All code must be verified with automated unit tests and SHA-256 receipts.",
        "Zero paid external API spend mandate.",
    ]
    for lim in report.get("limitations", []):
        text = lim if isinstance(lim, str) else str(lim)
        if text.strip():
            constraints.append(f"Analysis constraint: {text.strip()}")

    # 5. Unknowns become open questions (must be resolved before human approval)
    open_questions = [
        str(q).strip() for q in report.get("unknowns", []) if str(q).strip()
    ]

    spec = {
        "title": target_title,
        "goal": target_goal,
        "requirements": requirements,
        "open_questions": open_questions,
        "assumptions": assumptions,
        "constraints": constraints,
    }

    # Validate against core factory specification standards
    return _validate_spec(spec)

