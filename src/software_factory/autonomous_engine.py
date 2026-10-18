"""Autonomous Self-Healing Coding Loop and Reflection Engine.

Implements the iterative ReAct coding cycle:
1. Generate / Draft code via pluggable CodingAgentAdapter
2. Write code into the IsolatedWorkspace sandbox
3. Verify syntax, linter, or process test execution
4. If errors are detected, formulate a reflection feedback prompt
5. Autonomously self-heal and repair code until verified or budget reached
6. Persist unified diffs, test outputs, and zero-spend receipts into EvidenceStore
"""
from __future__ import annotations

import ast
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .agent_adapter import (
    AgentBudget,
    AutoSelectAgentAdapter,
    CodingAgentAdapter,
    QuotaExhaustedError,
)
from .evidence_store import EvidenceStore
from .sandbox import IsolatedWorkspace


def verify_code_syntax(file_path: str | Path, content: str) -> tuple[bool, str]:
    """Verify syntactic integrity of source code in-memory and return (passed, error_msg)."""
    p = Path(file_path)
    ext = p.suffix.lower()

    if ext == ".py":
        try:
            compile(content, p.name, "exec")
            return True, "Python AST syntax verified."
        except SyntaxError as e:
            return False, f"Python SyntaxError at line {e.lineno}, col {e.offset}: {e.msg}"

    if ext == ".json":
        try:
            json.loads(content)
            return True, "JSON format verified."
        except json.JSONDecodeError as e:
            return False, f"JSONDecodeError at line {e.lineno}, col {e.colno}: {e.msg}"

    if ext in (".ts", ".tsx", ".js", ".jsx"):
        # Check basic balanced delimiters
        pairs = {"{": "}", "(": ")", "[": "]"}
        stack: list[tuple[str, int]] = []
        in_string: str | None = None
        escaped = False

        for line_no, line in enumerate(content.splitlines(), start=1):
            col = 0
            while col < len(line):
                char = line[col]
                if escaped:
                    escaped = False
                    col += 1
                    continue
                if char == "\\":
                    escaped = True
                    col += 1
                    continue

                if in_string:
                    if char == in_string:
                        in_string = None
                else:
                    if char in ('"', "'", "`"):
                        in_string = char
                    elif char in pairs:
                        stack.append((char, line_no))
                    elif char in pairs.values():
                        if not stack:
                            return False, f"Unmatched closing '{char}' at line {line_no}"
                        opening, open_line = stack.pop()
                        if pairs[opening] != char:
                            return (
                                False,
                                f"Mismatched delimiter: opened '{opening}' at line {open_line}, closed with '{char}' at line {line_no}",
                            )
                col += 1

        if stack:
            unclosed, open_line = stack[-1]
            return False, f"Unclosed '{unclosed}' opened at line {open_line}"

        # Check export presence
        if not re.search(r"\b(export|import|function|class|interface|type|const)\b", content):
            return False, "TypeScript/JavaScript artifact contains no valid module exports or declarations."

        return True, "TypeScript/React syntax delimiters and module structure verified."

    # Default fallback
    return True, f"File format {ext} accepted."


@dataclass
class RepairAttempt:
    """Record of a single autonomous self-healing coding attempt."""
    iteration: int
    prompt: str
    code_generated: str
    verified: bool
    error_message: str = ""
    tokens_used: int = 0


class AutonomousCodingEngine:
    """Engine executing the autonomous write -> verify -> reflect -> repair loop."""

    def __init__(
        self,
        adapter: CodingAgentAdapter | None = None,
        evidence_store: EvidenceStore | None = None,
        max_repair_iterations: int = 3,
    ):
        self.adapter = adapter or AutoSelectAgentAdapter()
        self.evidence_store = evidence_store
        self.max_repair_iterations = max(1, max_repair_iterations)

    def execute_autonomous_task(
        self,
        workspace: IsolatedWorkspace,
        job_id: str,
        task_id: str,
        prompt: str,
        target_file: str,
        budget: AgentBudget | None = None,
        verification_command: str | None = None,
    ) -> dict[str, Any]:
        """Execute autonomous coding loop with self-healing reflection."""
        task_budget = budget or AgentBudget()
        attempts: list[RepairAttempt] = []
        prior_content = ""
        current_prompt = prompt
        last_error = ""

        # Check if target file already exists in workspace
        try:
            prior_content = workspace.read_file(target_file)
        except Exception:
            prior_content = ""

        final_status = "FAILED"
        final_code = ""

        for iteration in range(1, self.max_repair_iterations + 1):
            task_budget.check_call_allowed()

            if iteration > 1:
                current_prompt = (
                    f"The previous implementation of {target_file} produced errors during verification:\n"
                    f"--- COMPILER / VERIFICATION ERROR ---\n{last_error}\n--- END ERROR ---\n\n"
                    f"Please self-heal and fix the error. Return the complete corrected source code.\n"
                    f"Original requirement: {prompt}"
                )

            # 1. Generate code
            resp = self.adapter.generate(
                prompt=current_prompt,
                context={
                    "task_id": task_id,
                    "iteration": iteration,
                    "input": {"path": target_file},
                    "job_id": job_id,
                },
                budget=task_budget,
            )

            code = resp.code
            final_code = code

            # 2. Write to isolated workspace
            workspace.write_file(target_file, code)

            # 3. Record Diff in EvidenceStore
            attempt_id = f"attempt-{iteration}"
            if self.evidence_store:
                self.evidence_store.record_diff(
                    job_id=job_id,
                    task_id=task_id,
                    attempt_id=attempt_id,
                    file_path=target_file,
                    before_content=prior_content,
                    after_content=code,
                )

            # 4. Verify Syntax
            passed, err_msg = verify_code_syntax(target_file, code)

            # 5. Optional process test execution (e.g. npm test or python)
            if passed and verification_command:
                cmd_list = verification_command.split() if isinstance(verification_command, str) else list(verification_command)
                test_proc = workspace.run_command(cmd_list, timeout_seconds=15)
                rc = test_proc.get("return_code", -1)
                stdout = test_proc.get("stdout", "")
                stderr = test_proc.get("stderr", "")
                if rc != 0:
                    passed = False
                    err_msg = stderr or stdout or f"Process failed with exit code {rc}"

                if self.evidence_store:
                    self.evidence_store.record_test_log(
                        job_id=job_id,
                        task_id=task_id,
                        attempt_id=attempt_id,
                        command=verification_command,
                        exit_code=rc,
                        stdout=stdout,
                        stderr=stderr,
                    )

            attempts.append(
                RepairAttempt(
                    iteration=iteration,
                    prompt=current_prompt,
                    code_generated=code,
                    verified=passed,
                    error_message="" if passed else err_msg,
                    tokens_used=resp.tokens_used,
                )
            )

            if passed:
                final_status = "VERIFIED"
                break
            else:
                last_error = err_msg
                prior_content = code

        receipt = {
            "job_id": job_id,
            "task_id": task_id,
            "target_file": target_file,
            "status": final_status,
            "iterations_used": len(attempts),
            "attempts": [
                {
                    "iteration": a.iteration,
                    "verified": a.verified,
                    "error_message": a.error_message,
                    "tokens_used": a.tokens_used,
                }
                for a in attempts
            ],
            "final_code": final_code,
            "budget_tokens": task_budget.tokens_used,
            "zero_spend_compliant": task_budget.cost_usd == 0.0,
        }

        return receipt
