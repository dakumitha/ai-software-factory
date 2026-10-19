"""Standardized Agent Workspace Environment and CLAUDE.md / AGENT.md Generator.

Inspired by rse/claude-code-setup and rse/ase (https://github.com/rse/claude-code-setup),
this module automatically generates standardized development guidelines, lint rules,
build commands, and agent safety constraints into every scaffolded workspace.
"""
from __future__ import annotations

import json
from pathlib import Path


class AgentEnvironmentBootstrapper:
    """Bootstraps standardized configuration files for coding agents in a workspace."""

    @staticmethod
    def generate_claude_md(project_title: str = "Platform", tech_stack: str = "PNPM, Turbo, React, Vite, Firebase") -> str:
        """Generate standardized CLAUDE.md instruction file for coding assistants."""
        return (
            f"# {project_title} - Agentic Development Standards\n\n"
            f"## Technology Stack\n"
            f"- Architecture: Multi-stakeholder Monorepo (PNPM Workspaces + Turbo)\n"
            f"- Frontend: React 18, Vite, TypeScript, Tailwind CSS\n"
            f"- Backend / Database: Firebase Functions & Firestore (Modular SDK v9)\n"
            f"- Payments: Razorpay Standard Checkout & Webhooks\n"
            f"- Budget Limit: Strict ₹0 / $0 Cost Ceiling\n\n"
            f"## Standard Build & Test Commands\n"
            f"- Install Dependencies: `pnpm install`\n"
            f"- Build Monorepo: `pnpm run build` (or `turbo run build`)\n"
            f"- Run Test Suite: `pnpm test` (or `pytest tests/`)\n"
            f"- Lint & Typecheck: `pnpm run lint`\n\n"
            f"## Agent Coding & Safety Guidelines\n"
            f"1. **Zero-Spend Constraint**: Never introduce paid cloud fallbacks, billable APIs, or external paid licenses.\n"
            f"2. **Type Safety**: Strictly avoid `any` in TypeScript. Export modular interfaces in `packages/shared/types`.\n"
            f"3. **Security First**: Never hardcode API keys, secrets, or passwords. Extract them to `.env.local`.\n"
            f"4. **Atomic Commits**: Ensure code compiles before submitting diffs for release evaluation.\n"
        )

    @staticmethod
    def generate_agent_config(project_title: str = "Platform") -> dict[str, Any]:
        """Generate machine-readable agent configuration and tool metadata."""
        return {
            "$schema": "https://software-factory.local/schemas/agent-config.v1.json",
            "project_title": project_title,
            "version": "1.0.0",
            "allowed_commands": ["npm", "pnpm", "node", "git", "python", "pytest"],
            "security": {
                "strict_zero_spend": True,
                "allow_network_billing": False,
                "secret_scanning_enforced": True,
            },
            "squads": [
                "backend_core",
                "customer_web",
                "customer_mobile",
                "seller_portal",
                "rider_dispatch",
                "admin_operations",
                "security_audit",
                "qa_verification",
            ],
        }

    def bootstrap_workspace(self, workspace_path: str | Path, project_title: str = "Platform") -> list[str]:
        """Write CLAUDE.md, AGENT.md, and .agent/config.json into the target workspace."""
        root = Path(workspace_path)
        root.mkdir(parents=True, exist_ok=True)
        written = []

        claude_md_path = root / "CLAUDE.md"
        claude_md_content = self.generate_claude_md(project_title)
        claude_md_path.write_text(claude_md_content, encoding="utf-8")
        written.append(str(claude_md_path))

        agent_md_path = root / "AGENT.md"
        agent_md_path.write_text(claude_md_content, encoding="utf-8")
        written.append(str(agent_md_path))

        agent_dir = root / ".agent"
        agent_dir.mkdir(parents=True, exist_ok=True)
        config_path = agent_dir / "config.json"
        config_path.write_text(json.dumps(self.generate_agent_config(project_title), indent=2) + "\n", encoding="utf-8")
        written.append(str(config_path))

        return written

