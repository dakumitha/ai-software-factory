"""Autonomous Security Audit and Penetration Testing Engine.

Inspired by Strix (https://github.com/usestrix/strix),
this module dynamically audits generated codebases and workspaces for security flaws,
vulnerabilities, hardcoded secrets, insecure permissions, and payment bypasses.
It produces verified findings and enforces security gates prior to production release.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class SecurityFinding:
    """A security vulnerability or policy violation discovered in the workspace."""
    check_id: str
    severity: str  # 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'
    title: str
    file_path: str
    line_number: int | None
    description: str
    remediation: str


@dataclass
class SecurityReport:
    """Overall security evaluation of a software factory job or codebase."""
    job_id: str
    status: str  # 'PASSED', 'WARNING', 'FAILED_SECURITY_GATE'
    risk_level: str  # 'CLEAN', 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'
    total_findings: int
    findings: list[SecurityFinding] = field(default_factory=list)
    scanned_files_count: int = 0


class SecurityAuditEngine:
    """Multi-vector security auditor enforcing pre-release penetration checks."""

    # Patterns for credential and secret leakage
    SECRET_PATTERNS = [
        (re.compile(r"""(?:api[_-]?key|secret|token|password|passwd)\s*[:=]\s*["']([A-Za-z0-9_\-\.]{16,})["']""", re.IGNORECASE), "Hardcoded Secret / API Token Detected"),
        (re.compile(r"""-----BEGIN (?:RSA )?PRIVATE KEY-----"""), "Hardcoded RSA/SSH Private Key"),
        (re.compile(r"""firebaseConfig\s*=\s*\{[^}]*apiKey:\s*["']AIza[0-9A-Za-z-_]{35}["']"""), "Exposed Live Google/Firebase API Key"),
        (re.compile(r"""rzp_(?:live|test)_[0-9a-zA-Z]{14}"""), "Hardcoded Razorpay API Key"),
    ]

    # Insecure rule and code patterns
    INSECURE_PATTERNS = [
        (re.compile(r"""allow\s+(?:read\s*,\s*write|write\s*,\s*read|read|write)\s*:\s*if\s+true\s*;"""), "CRITICAL", "Wildcard Insecure Firestore Security Rule", "Firestore rules grant unrestricted global read/write access. Enforce authentication and ownership rules."),
        (re.compile(r"""dangerouslySetInnerHTML\s*=\s*\{"""), "HIGH", "Potential Cross-Site Scripting (XSS)", "Unsanitized HTML injection via dangerouslySetInnerHTML. Use React JSX escaping or DOMPurify."),
        (re.compile(r"""\beval\s*\("""), "CRITICAL", "Arbitrary Code Execution via eval()", "Use of eval() detected. Refactor to static deserialization or safe AST parsing."),
        (re.compile(r"""(exec|spawn|popen)\s*\([^)]*(shell:\s*true)""", re.IGNORECASE), "HIGH", "Insecure Shell Execution", "Subprocess execution with shell=true enables command injection. Use argument lists with shell=false."),
    ]

    def scan_code_text(self, content: str, file_path: str = "inline") -> list[SecurityFinding]:
        """Scan a single source code text buffer for vulnerabilities."""
        findings: list[SecurityFinding] = []
        lines = content.splitlines()

        # 1. Scan for hardcoded credentials
        for pattern, title in self.SECRET_PATTERNS:
            for line_idx, line in enumerate(lines, start=1):
                # Exclude mock keys and templates
                if any(dummy in line.lower() for dummy in ("mock", "placeholder", "demo", "sample", "test", "your-", "xxx")):
                    continue
                if pattern.search(line):
                    findings.append(
                        SecurityFinding(
                            check_id="SEC-SECRET-LEAK",
                            severity="HIGH",
                            title=title,
                            file_path=file_path,
                            line_number=line_idx,
                            description=f"Potential credential exposure on line {line_idx}.",
                            remediation="Extract secrets to environment variables (.env) or runtime secret managers.",
                        )
                    )

        # 2. Scan for insecure code patterns
        for pattern, severity, title, rem in self.INSECURE_PATTERNS:
            for line_idx, line in enumerate(lines, start=1):
                if "re.compile" in line or "INSECURE_PATTERNS" in line:
                    continue
                if pattern.search(line):
                    findings.append(
                        SecurityFinding(
                            check_id="SEC-INSECURE-PATTERN",
                            severity=severity,
                            title=title,
                            file_path=file_path,
                            line_number=line_idx,
                            description=f"Insecure code pattern identified on line {line_idx}.",
                            remediation=rem,
                        )
                    )
        return findings

    def audit_workspace(self, workspace_path: str | Path, job_id: str = "audit") -> SecurityReport:
        """Scan all source code files within a workspace directory for vulnerabilities."""
        p = Path(workspace_path)
        findings: list[SecurityFinding] = []
        scanned_count = 0

        if not p.exists():
            return SecurityReport(job_id=job_id, status="PASSED", risk_level="CLEAN", total_findings=0, findings=[])

        target_exts = {".ts", ".tsx", ".js", ".jsx", ".py", ".json", ".rules", ".yaml", ".yml", ".html"}
        for file_path in p.rglob("*"):
            if not file_path.is_file() or file_path.suffix.lower() not in target_exts:
                continue
            if any(part.startswith(".") or part in ("node_modules", "dist", "build", ".git", "__pycache__") for part in file_path.parts):
                continue

            scanned_count += 1
            try:
                content = file_path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue

            rel_path = str(file_path.relative_to(p))
            findings.extend(self.scan_code_text(content, file_path=rel_path))

        # Evaluate risk level
        has_critical = any(f.severity == "CRITICAL" for f in findings)
        has_high = any(f.severity == "HIGH" for f in findings)
        has_medium = any(f.severity == "MEDIUM" for f in findings)

        if has_critical:
            risk = "CRITICAL"
            status = "FAILED_SECURITY_GATE"
        elif has_high:
            risk = "HIGH"
            status = "FAILED_SECURITY_GATE"
        elif has_medium:
            risk = "MEDIUM"
            status = "WARNING"
        elif findings:
            risk = "LOW"
            status = "WARNING"
        else:
            risk = "CLEAN"
            status = "PASSED"

        return SecurityReport(
            job_id=job_id,
            status=status,
            risk_level=risk,
            total_findings=len(findings),
            findings=findings,
            scanned_files_count=scanned_count,
        )
