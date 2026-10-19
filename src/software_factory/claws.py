"""Lightweight Claw Bridge and Multi-Channel Chat Webhook Connector.

Inspired by awesome-claws (https://github.com/machinae/awesome-claws),
this module allows developers and operators to monitor, control, and trigger
the AI Software Factory directly from chat apps (WhatsApp, Telegram, Discord, Slack)
and headless webhook dispatchers.
"""
from __future__ import annotations

import hmac
import hashlib
import json
import time
from dataclasses import dataclass
from typing import Any, Callable

from .core import Store


@dataclass
class ClawCommand:
    """Parsed command received from a chat app or webhook."""
    action: str  # 'status', 'build', 'release', 'audit'
    args: list[str]
    sender_id: str
    channel: str  # 'telegram', 'whatsapp', 'discord', 'webhook'
    raw_text: str


@dataclass
class ClawResponse:
    """Formatted response to return to the messaging channel."""
    markdown_text: str
    action_performed: str
    success: bool
    data: dict[str, Any]


class ClawBridge:
    """Gateway connecting chat platforms and webhooks to factory orchestration."""

    def __init__(self, store: Store, webhook_secret: str = ""):
        self.store = store
        self.secret = webhook_secret

    def verify_signature(self, payload_bytes: bytes, signature_header: str) -> bool:
        """Verify HMAC-SHA256 signature if a webhook secret is configured."""
        if not self.secret:
            return True  # Open local development mode
        expected = hmac.new(self.secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature_header)

    def parse_webhook_payload(self, payload: dict[str, Any], channel: str = "webhook") -> ClawCommand:
        """Normalize disparate chat payloads into a standard ClawCommand."""
        # Standard generic webhook or Telegram format
        text = ""
        sender = "anonymous"

        if "message" in payload and "text" in payload["message"]:
            # Telegram format
            text = payload["message"]["text"]
            sender = str(payload["message"].get("from", {}).get("username", "telegram-user"))
            channel = "telegram"
        elif "content" in payload:
            # Discord format
            text = payload["content"]
            sender = str(payload.get("author", {}).get("username", "discord-user"))
            channel = "discord"
        elif "text" in payload:
            # Slack / generic format
            text = payload["text"]
            sender = str(payload.get("user_name", payload.get("sender", "bot-user")))
        else:
            text = str(payload.get("command", "/status"))

        tokens = text.strip().split()
        cmd = tokens[0].lower() if tokens else "/status"
        if cmd.startswith("/"):
            cmd = cmd[1:]
        args = tokens[1:] if len(tokens) > 1 else []

        return ClawCommand(
            action=cmd,
            args=args,
            sender_id=sender,
            channel=channel,
            raw_text=text,
        )

    def execute_command(self, cmd: ClawCommand) -> ClawResponse:
        """Execute the command against the software factory state machine."""
        if cmd.action in ("status", "health", "ping"):
            jobs = self.store.list_jobs()
            active_count = sum(1 for j in jobs if j["state"] in ("RUNNING", "VERIFYING", "CLAIMED"))
            released_count = sum(1 for j in jobs if j["state"] == "RELEASED")

            text = (
                f"🤖 *AI Software Factory Status*\n\n"
                f"• Active Jobs: `{active_count}`\n"
                f"• Released Production Apps: `{released_count}`\n"
                f"• Total Jobs in DB: `{len(jobs)}`\n"
                f"• Zero-Spend Policy: `₹0 ($0.00) Enforced`\n"
            )
            return ClawResponse(markdown_text=text, action_performed="status", success=True, data={"jobs_count": len(jobs)})

        if cmd.action in ("build", "create", "scaffold"):
            archetype = cmd.args[0] if cmd.args else "school_transport"
            prj = self.store.create_project(name=f"Chat App Project ({archetype})", idea=f"Triggered via {cmd.channel} by {cmd.sender_id}")
            job = self.store.create_job(project_id=prj["id"], spec={"title": f"App ({archetype})", "archetype": archetype})

            text = (
                f"🚀 *New Job Initialized via {cmd.channel.title()}!*\n\n"
                f"• Job ID: `{job['id']}`\n"
                f"• Archetype: `{archetype}`\n"
                f"• State: `{job['state']}`\n"
                f"• Started by: `{cmd.sender_id}`\n"
            )
            return ClawResponse(markdown_text=text, action_performed="build", success=True, data={"job_id": job["id"]})

        if cmd.action == "audit" and cmd.args:
            target_job_id = cmd.args[0]
            from .security import SecurityAuditEngine
            from .sandbox import IsolatedWorkspace
            ws_path = Path("workspace") / target_job_id
            auditor = SecurityAuditEngine()
            report = auditor.audit_workspace(ws_path, job_id=target_job_id)

            text = (
                f"🛡️ *Security Audit Report (Strix Engine)*\n\n"
                f"• Job: `{target_job_id}`\n"
                f"• Status: `{report.status}`\n"
                f"• Risk Level: `{report.risk_level}`\n"
                f"• Findings: `{report.total_findings}`\n"
                f"• Scanned Files: `{report.scanned_files_count}`\n"
            )
            return ClawResponse(markdown_text=text, action_performed="audit", success=True, data={"report": report.__dict__})

        return ClawResponse(
            markdown_text=f"Unknown command `/{cmd.action}`. Supported: `/status`, `/build [archetype]`, `/audit [job_id]`",
            action_performed="unknown",
            success=False,
            data={},
        )

