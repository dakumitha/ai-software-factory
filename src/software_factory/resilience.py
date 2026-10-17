"""Bounded retry policy and adapter circuit breakers for reliable worker execution.

This module implements deterministic retry evaluation, idempotency key generation,
and a 3-state circuit breaker (CLOSED, OPEN, HALF_OPEN) for protecting external
adapters and worker handlers from continuous failing loops and resource exhaustion.
"""
from __future__ import annotations

import hashlib
import json
import threading
from datetime import datetime, timezone
from typing import Any

from .heartbeat import RETRYABLE_OUTCOME_CATEGORIES, sanitize_error

# Circuit breaker states
CIRCUIT_CLOSED = "CLOSED"
CIRCUIT_OPEN = "OPEN"
CIRCUIT_HALF_OPEN = "HALF_OPEN"


class CircuitBreakerError(RuntimeError):
    """Raised or returned when execution is blocked because a circuit breaker is OPEN."""


def derive_idempotency_key(task_id: str, payload: Any = None) -> str:
    """Derive a stable, deterministic idempotency key from task ID and canonical input payload.

    Uses SHA-256 over task identity and sorted canonical JSON representation.
    """
    if not isinstance(task_id, str) or not task_id.strip():
        raise ValueError("task_id must be a non-empty string")

    try:
        canonical_payload = json.dumps(payload or {}, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Payload cannot be canonically serialized to JSON: {exc}") from exc

    raw_fingerprint = f"{task_id}:{canonical_payload}".encode("utf-8")
    digest = hashlib.sha256(raw_fingerprint).hexdigest()[:32]
    return f"idem_{digest}"


class CircuitBreaker:
    """Three-state circuit breaker (CLOSED, OPEN, HALF_OPEN) for adapters and handlers.

    Guards workers and external providers from repeated cascading failures.
    Deterministic, thread-safe, and supports injected timestamps for testability.
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 3,
        recovery_timeout_seconds: float = 60.0,
        half_open_success_threshold: int = 1,
    ):
        if not isinstance(name, str) or not name.strip():
            raise ValueError("name must be a non-empty string")
        if failure_threshold < 1:
            raise ValueError("failure_threshold must be at least 1")
        if recovery_timeout_seconds <= 0:
            raise ValueError("recovery_timeout_seconds must be positive")
        if half_open_success_threshold < 1:
            raise ValueError("half_open_success_threshold must be at least 1")

        self.name = name.strip()
        self.failure_threshold = int(failure_threshold)
        self.recovery_timeout_seconds = float(recovery_timeout_seconds)
        self.half_open_success_threshold = int(half_open_success_threshold)

        self._lock = threading.Lock()
        self._state = CIRCUIT_CLOSED
        self._consecutive_failures = 0
        self._consecutive_successes = 0
        self._last_failure_at: datetime | None = None
        self._last_failure_reason: str = ""
        self._tripped_at: datetime | None = None

    @property
    def state(self) -> str:
        with self._lock:
            return self._state

    def allow_execution(self, now: datetime | None = None) -> tuple[bool, str]:
        """Check whether execution is permitted under the current circuit state.

        Returns (allowed: bool, reason: str).
        """
        current_time = now or datetime.now(timezone.utc)
        with self._lock:
            if self._state == CIRCUIT_CLOSED:
                return True, "OK"

            if self._state == CIRCUIT_OPEN:
                if self._tripped_at is None:
                    self._tripped_at = current_time

                elapsed = (current_time - self._tripped_at).total_seconds()
                if elapsed >= self.recovery_timeout_seconds:
                    self._state = CIRCUIT_HALF_OPEN
                    self._consecutive_successes = 0
                    return True, f"Circuit '{self.name}' entered HALF_OPEN state; probe permitted."

                remaining = max(0.0, self.recovery_timeout_seconds - elapsed)
                return False, (
                    f"Circuit '{self.name}' is OPEN. "
                    f"Reason: {self._last_failure_reason or 'Failure threshold reached'}; "
                    f"cool-down remaining: {remaining:.1f}s."
                )

            if self._state == CIRCUIT_HALF_OPEN:
                return True, f"Circuit '{self.name}' is HALF_OPEN; probe in progress."

            return False, f"Unknown circuit state '{self._state}'"

    def record_success(self) -> None:
        """Record a successful operation, restoring OPEN/HALF_OPEN circuits to CLOSED."""
        with self._lock:
            if self._state == CIRCUIT_HALF_OPEN:
                self._consecutive_successes += 1
                if self._consecutive_successes >= self.half_open_success_threshold:
                    self._state = CIRCUIT_CLOSED
                    self._consecutive_failures = 0
                    self._consecutive_successes = 0
                    self._tripped_at = None
                    self._last_failure_reason = ""
            elif self._state == CIRCUIT_CLOSED:
                self._consecutive_failures = 0

    def record_failure(
        self,
        category: str,
        error: str = "",
        now: datetime | None = None,
    ) -> None:
        """Record an operation failure, tripping the circuit to OPEN if threshold is reached."""
        current_time = now or datetime.now(timezone.utc)
        sanitized_error = sanitize_error(error, max_chars=200) if error else ""
        with self._lock:
            self._consecutive_failures += 1
            self._last_failure_at = current_time
            self._last_failure_reason = f"[{category}] {sanitized_error}".strip()

            if self._state == CIRCUIT_HALF_OPEN or self._consecutive_failures >= self.failure_threshold:
                self._state = CIRCUIT_OPEN
                self._tripped_at = current_time
                self._consecutive_successes = 0

    def reset(self) -> None:
        """Reset the circuit breaker to closed state."""
        with self._lock:
            self._state = CIRCUIT_CLOSED
            self._consecutive_failures = 0
            self._consecutive_successes = 0
            self._tripped_at = None
            self._last_failure_at = None
            self._last_failure_reason = ""

    def status(self, now: datetime | None = None) -> dict[str, Any]:
        """Return diagnostic status for reporting and human review."""
        current_time = now or datetime.now(timezone.utc)
        with self._lock:
            tripped_str = self._tripped_at.isoformat() if self._tripped_at else None
            last_fail_str = self._last_failure_at.isoformat() if self._last_failure_at else None
            elapsed = (current_time - self._tripped_at).total_seconds() if self._tripped_at else 0.0
            remaining = max(0.0, self.recovery_timeout_seconds - elapsed) if self._state == CIRCUIT_OPEN else 0.0

            return {
                "name": self.name,
                "state": self._state,
                "failure_threshold": self.failure_threshold,
                "consecutive_failures": self._consecutive_failures,
                "recovery_timeout_seconds": self.recovery_timeout_seconds,
                "cool_down_remaining_seconds": round(remaining, 2),
                "tripped_at": tripped_str,
                "last_failure_at": last_fail_str,
                "last_failure_reason": self._last_failure_reason,
            }


class CircuitBreakerRegistry:
    """Registry maintaining named circuit breaker instances."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._breakers: dict[str, CircuitBreaker] = {}

    def get_or_create(
        self,
        name: str,
        failure_threshold: int = 3,
        recovery_timeout_seconds: float = 60.0,
        half_open_success_threshold: int = 1,
    ) -> CircuitBreaker:
        """Retrieve existing circuit breaker or instantiate a new one."""
        with self._lock:
            if name not in self._breakers:
                self._breakers[name] = CircuitBreaker(
                    name=name,
                    failure_threshold=failure_threshold,
                    recovery_timeout_seconds=recovery_timeout_seconds,
                    half_open_success_threshold=half_open_success_threshold,
                )
            return self._breakers[name]

    def get(self, name: str) -> CircuitBreaker | None:
        """Retrieve named circuit breaker if it exists."""
        with self._lock:
            return self._breakers.get(name)

    def reset_all(self) -> None:
        """Reset all registered circuit breakers."""
        with self._lock:
            for breaker in self._breakers.values():
                breaker.reset()


class RetryPolicy:
    """Deterministic, bounded retry policy.

    Enforces:
    1. Maximum retry limits to prevent runaway loops.
    2. Strict outcome category allowlisting (non-retryable errors are immediately halted).
    3. Non-idempotent side-effect prohibition (automatic retry forbidden unless marked idempotent).
    4. Deterministic backoff computation without external dependencies.
    """

    def __init__(
        self,
        max_retries: int = 3,
        initial_backoff_seconds: float = 1.0,
        backoff_multiplier: float = 2.0,
        max_backoff_seconds: float = 60.0,
        retryable_categories: frozenset[str] | None = None,
    ):
        if max_retries < 0:
            raise ValueError("max_retries must be non-negative")
        if initial_backoff_seconds < 0:
            raise ValueError("initial_backoff_seconds must be non-negative")
        if backoff_multiplier < 1.0:
            raise ValueError("backoff_multiplier must be at least 1.0")
        if max_backoff_seconds < initial_backoff_seconds:
            raise ValueError("max_backoff_seconds cannot be less than initial_backoff_seconds")

        self.max_retries = int(max_retries)
        self.initial_backoff_seconds = float(initial_backoff_seconds)
        self.backoff_multiplier = float(backoff_multiplier)
        self.max_backoff_seconds = float(max_backoff_seconds)
        self.retryable_categories = (
            frozenset(retryable_categories)
            if retryable_categories is not None
            else RETRYABLE_OUTCOME_CATEGORIES
        )

    def calculate_backoff(self, attempt_count: int) -> float:
        """Calculate deterministic exponential backoff delay for the next attempt."""
        if attempt_count <= 0:
            return 0.0
        delay = self.initial_backoff_seconds * (self.backoff_multiplier ** (attempt_count - 1))
        return round(min(self.max_backoff_seconds, delay), 3)

    def evaluate(
        self,
        task_id: str,
        outcome: dict[str, Any],
        attempt_count: int,
        is_idempotent: bool = False,
        task_payload: Any = None,
    ) -> dict[str, Any]:
        """Evaluate whether a failed task may be retried under policy.

        Returns a structured RetryDecision record.
        """
        category = outcome.get("category", "")
        idempotency_key = derive_idempotency_key(task_id, task_payload) if is_idempotent else None

        if category not in self.retryable_categories:
            return {
                "should_retry": False,
                "task_id": task_id,
                "category": category,
                "attempt_count": attempt_count,
                "max_retries": self.max_retries,
                "backoff_seconds": 0.0,
                "reason": f"Outcome category '{category}' is non-retryable by policy.",
                "idempotency_key": idempotency_key,
            }

        if attempt_count >= self.max_retries:
            return {
                "should_retry": False,
                "task_id": task_id,
                "category": category,
                "attempt_count": attempt_count,
                "max_retries": self.max_retries,
                "backoff_seconds": 0.0,
                "reason": f"Maximum retry ceiling of {self.max_retries} attempts reached for task '{task_id}'.",
                "idempotency_key": idempotency_key,
            }

        if not is_idempotent:
            return {
                "should_retry": False,
                "task_id": task_id,
                "category": category,
                "attempt_count": attempt_count,
                "max_retries": self.max_retries,
                "backoff_seconds": 0.0,
                "reason": (
                    f"Task '{task_id}' is not declared idempotent; "
                    "automatic retry prohibited to prevent duplicate side effects."
                ),
                "idempotency_key": None,
            }

        next_attempt = attempt_count + 1
        backoff = self.calculate_backoff(next_attempt)
        return {
            "should_retry": True,
            "task_id": task_id,
            "category": category,
            "attempt_count": attempt_count,
            "max_retries": self.max_retries,
            "backoff_seconds": backoff,
            "reason": f"Eligible for bounded retry (attempt {next_attempt} of {self.max_retries}).",
            "idempotency_key": idempotency_key,
        }

