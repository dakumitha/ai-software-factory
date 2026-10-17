"""Heartbeat renewal manager and structured task outcome records.

This module provides background lease heartbeats for active workers and
standardized outcome diagnostics. It enforces secret sanitization and
explicit retry eligibility according to the reliability contract.
"""
from __future__ import annotations

import re
import threading
import time
from datetime import datetime, timezone
from typing import Any

from .core import Store, ValidationError, utc_now

# Standard outcome categories
OUTCOME_SUCCESS = "SUCCESS"
OUTCOME_TIMEOUT = "TIMEOUT"
OUTCOME_HANDLER_ERROR = "HANDLER_ERROR"
OUTCOME_PAYLOAD_INVALID = "PAYLOAD_INVALID"
OUTCOME_OUTPUT_LIMIT_EXCEEDED = "OUTPUT_LIMIT_EXCEEDED"
OUTCOME_INTERRUPTED = "INTERRUPTED"

# Explicit retry eligibility policy
RETRYABLE_OUTCOME_CATEGORIES = frozenset({
    OUTCOME_TIMEOUT,
    OUTCOME_HANDLER_ERROR,
})

NON_RETRYABLE_OUTCOME_CATEGORIES = frozenset({
    OUTCOME_SUCCESS,
    OUTCOME_PAYLOAD_INVALID,
    OUTCOME_OUTPUT_LIMIT_EXCEEDED,
    OUTCOME_INTERRUPTED,
})

# Secret sanitization patterns
_SECRET_PATTERNS = [
    (re.compile(r"(?i)\b(bearer\s+)[A-Za-z0-9_\-\.]{12,}\b"), r"\1[REDACTED]"),
    (re.compile(r"(?i)\b([a-z0-9_]*(?:key|token|secret|password|passwd|auth)[a-z0-9_]*)\s*([:=])\s*['\"]?[^\s'\",;&]+['\"]?"), r"\1\2[REDACTED]"),
    (re.compile(r"\b[A-Fa-f0-9]{32,64}\b"), r"[REDACTED_HEX_TOKEN]"),
]


def sanitize_error(text: str, max_chars: int = 1000) -> str:
    """Sanitize error messages by redacting common secret tokens, credentials, and keys."""
    if not isinstance(text, str):
        text = str(text)
    sanitized = text
    for pattern, replacement in _SECRET_PATTERNS:
        sanitized = pattern.sub(replacement, sanitized)
    return sanitized[:max_chars]


def build_task_outcome(
    category: str,
    duration_ms: int,
    task_id: str,
    attempt_id: str,
    error: str = "",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a structured task outcome record with explicit retry eligibility."""
    return {
        "category": category,
        "duration_ms": max(0, int(duration_ms)),
        "task_id": task_id,
        "attempt_id": attempt_id,
        "retry_eligible": category in RETRYABLE_OUTCOME_CATEGORIES,
        "error_summary": sanitize_error(error) if error else "",
        "metadata": metadata or {},
    }


class HeartbeatKeeper:
    """Context manager that periodically renews a worker lease in the background.

    Runs a background daemon thread during long-running task execution to prevent
    unintended lease expiration. Terminates cleanly on block exit.
    """

    def __init__(
        self,
        store: Store,
        job_id: str,
        token: str,
        interval_seconds: float = 15.0,
        ttl_seconds: int = 60,
    ):
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be positive")
        if ttl_seconds < 10:
            raise ValueError("ttl_seconds must be at least 10 seconds")
        self.store = store
        self.job_id = job_id
        self.token = token
        self.interval_seconds = float(interval_seconds)
        self.ttl_seconds = int(ttl_seconds)

        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self.heartbeat_count = 0
        self.last_heartbeat_at: str | None = None
        self.last_error: Exception | None = None

    def __enter__(self) -> HeartbeatKeeper:
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run_loop,
            name=f"HeartbeatKeeper-{self.job_id}",
            daemon=True,
        )
        self._thread.start()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            # Wait for interval or until stopped
            if self._stop_event.wait(timeout=self.interval_seconds):
                break
            try:
                result = self.store.heartbeat_lease(
                    self.job_id,
                    self.token,
                    ttl_seconds=self.ttl_seconds,
                )
                self.heartbeat_count += 1
                self.last_heartbeat_at = result["heartbeat_at"]
            except Exception as exc:
                self.last_error = exc
                # If lease was revoked or token became invalid, stop beating
                break

