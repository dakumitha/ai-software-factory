"""Tests for bounded retry policy, idempotency keys, and circuit breakers."""
import unittest
from datetime import datetime, timedelta, timezone

from software_factory.heartbeat import (
    OUTCOME_HANDLER_ERROR,
    OUTCOME_INTERRUPTED,
    OUTCOME_OUTPUT_LIMIT_EXCEEDED,
    OUTCOME_PAYLOAD_INVALID,
    OUTCOME_SUCCESS,
    OUTCOME_TIMEOUT,
    build_task_outcome,
)
from software_factory.resilience import (
    CIRCUIT_CLOSED,
    CIRCUIT_HALF_OPEN,
    CIRCUIT_OPEN,
    CircuitBreaker,
    CircuitBreakerRegistry,
    RetryPolicy,
    derive_idempotency_key,
)


class ResilienceTests(unittest.TestCase):
    def test_derive_idempotency_key_deterministic_and_order_invariant(self):
        payload_a = {"alpha": 1, "beta": "two", "nested": {"x": 10, "y": 20}}
        payload_b = {"nested": {"y": 20, "x": 10}, "beta": "two", "alpha": 1}

        key_a = derive_idempotency_key("task-123", payload_a)
        key_b = derive_idempotency_key("task-123", payload_b)

        self.assertTrue(key_a.startswith("idem_"))
        self.assertEqual(key_a, key_b)

        # Different task id or payload produces different key
        key_diff_task = derive_idempotency_key("task-456", payload_a)
        key_diff_payload = derive_idempotency_key("task-123", {"alpha": 2})

        self.assertNotEqual(key_a, key_diff_task)
        self.assertNotEqual(key_a, key_diff_payload)

    def test_derive_idempotency_key_validations(self):
        with self.assertRaises(ValueError):
            derive_idempotency_key("")

        with self.assertRaises(ValueError):
            derive_idempotency_key("   ")

        with self.assertRaises(ValueError):
            derive_idempotency_key("task-1", {1, 2, 3})  # set is not JSON serializable

    def test_circuit_breaker_initial_state_and_success(self):
        breaker = CircuitBreaker("test-adapter", failure_threshold=3)
        self.assertEqual(breaker.state, CIRCUIT_CLOSED)

        allowed, reason = breaker.allow_execution()
        self.assertTrue(allowed)
        self.assertEqual(reason, "OK")

        breaker.record_success()
        self.assertEqual(breaker.state, CIRCUIT_CLOSED)

    def test_circuit_breaker_trips_to_open_after_threshold(self):
        breaker = CircuitBreaker("api-adapter", failure_threshold=2, recovery_timeout_seconds=30.0)
        t0 = datetime(2026, 10, 17, 12, 0, 0, tzinfo=timezone.utc)

        # First failure: remains CLOSED
        breaker.record_failure(OUTCOME_HANDLER_ERROR, error="Connection refused", now=t0)
        self.assertEqual(breaker.state, CIRCUIT_CLOSED)
        allowed, _ = breaker.allow_execution(now=t0)
        self.assertTrue(allowed)

        # Second failure: trips to OPEN
        breaker.record_failure(OUTCOME_HANDLER_ERROR, error="secret_token=abc1234567890", now=t0)
        self.assertEqual(breaker.state, CIRCUIT_OPEN)

        # Blocked while cool-down has not elapsed
        t_blocked = t0 + timedelta(seconds=10)
        allowed, reason = breaker.allow_execution(now=t_blocked)
        self.assertFalse(allowed)
        self.assertIn("OPEN", reason)
        self.assertNotIn("abc1234567890", reason)  # Secret must be sanitized
        self.assertIn("cool-down remaining: 20.0s", reason)

    def test_circuit_breaker_transitions_to_half_open_and_recovers(self):
        breaker = CircuitBreaker(
            "half-open-test",
            failure_threshold=1,
            recovery_timeout_seconds=10.0,
            half_open_success_threshold=2,
        )
        t0 = datetime(2026, 10, 17, 12, 0, 0, tzinfo=timezone.utc)
        breaker.record_failure(OUTCOME_TIMEOUT, error="Read timeout", now=t0)
        self.assertEqual(breaker.state, CIRCUIT_OPEN)

        # Fast forward past recovery timeout
        t_half_open = t0 + timedelta(seconds=11)
        allowed, reason = breaker.allow_execution(now=t_half_open)
        self.assertTrue(allowed)
        self.assertEqual(breaker.state, CIRCUIT_HALF_OPEN)
        self.assertIn("HALF_OPEN", reason)

        # First probe success: still HALF_OPEN
        breaker.record_success()
        self.assertEqual(breaker.state, CIRCUIT_HALF_OPEN)

        # Second probe success: reaches threshold (2) -> recovers to CLOSED
        breaker.record_success()
        self.assertEqual(breaker.state, CIRCUIT_CLOSED)
        allowed, _ = breaker.allow_execution(now=t_half_open)
        self.assertTrue(allowed)

    def test_circuit_breaker_trips_immediately_on_failure_in_half_open(self):
        breaker = CircuitBreaker("probe-fail", failure_threshold=3, recovery_timeout_seconds=10.0)
        t0 = datetime(2026, 10, 17, 12, 0, 0, tzinfo=timezone.utc)
        breaker.record_failure(OUTCOME_TIMEOUT, error="Trip", now=t0)
        breaker.record_failure(OUTCOME_TIMEOUT, error="Trip", now=t0)
        breaker.record_failure(OUTCOME_TIMEOUT, error="Trip", now=t0)
        self.assertEqual(breaker.state, CIRCUIT_OPEN)

        # Move to HALF_OPEN
        t_probe = t0 + timedelta(seconds=12)
        breaker.allow_execution(now=t_probe)
        self.assertEqual(breaker.state, CIRCUIT_HALF_OPEN)

        # Single failure in HALF_OPEN trips immediately back to OPEN
        breaker.record_failure(OUTCOME_TIMEOUT, error="Probe failed", now=t_probe)
        self.assertEqual(breaker.state, CIRCUIT_OPEN)

    def test_circuit_breaker_registry(self):
        registry = CircuitBreakerRegistry()
        cb1 = registry.get_or_create("adapter-a", failure_threshold=2)
        cb2 = registry.get_or_create("adapter-a")
        self.assertIs(cb1, cb2)

        cb1.record_failure("ERR", "fail")
        cb1.record_failure("ERR", "fail")
        self.assertEqual(cb1.state, CIRCUIT_OPEN)

        registry.reset_all()
        self.assertEqual(cb1.state, CIRCUIT_CLOSED)

    def test_retry_policy_deterministic_backoff(self):
        policy = RetryPolicy(
            max_retries=4,
            initial_backoff_seconds=1.5,
            backoff_multiplier=2.0,
            max_backoff_seconds=10.0,
        )
        self.assertEqual(policy.calculate_backoff(0), 0.0)
        self.assertEqual(policy.calculate_backoff(1), 1.5)
        self.assertEqual(policy.calculate_backoff(2), 3.0)
        self.assertEqual(policy.calculate_backoff(3), 6.0)
        self.assertEqual(policy.calculate_backoff(4), 10.0)  # Capped at max_backoff_seconds
        self.assertEqual(policy.calculate_backoff(5), 10.0)

    def test_retry_policy_rejects_non_retryable_categories(self):
        policy = RetryPolicy(max_retries=3)
        non_retryable = [
            OUTCOME_SUCCESS,
            OUTCOME_PAYLOAD_INVALID,
            OUTCOME_OUTPUT_LIMIT_EXCEEDED,
            OUTCOME_INTERRUPTED,
        ]

        for cat in non_retryable:
            outcome = build_task_outcome(cat, 100, "task-1", "attempt-1")
            decision = policy.evaluate("task-1", outcome, attempt_count=1, is_idempotent=True)
            self.assertFalse(decision["should_retry"])
            self.assertEqual(decision["backoff_seconds"], 0.0)
            self.assertIn("non-retryable", decision["reason"])

    def test_retry_policy_blocks_non_idempotent_side_effects(self):
        policy = RetryPolicy(max_retries=3)
        outcome = build_task_outcome(OUTCOME_HANDLER_ERROR, 200, "task-side-effect", "attempt-1")

        # Non-idempotent task cannot be automatically retried
        decision = policy.evaluate(
            "task-side-effect",
            outcome,
            attempt_count=1,
            is_idempotent=False,
            task_payload={"action": "write_external"},
        )
        self.assertFalse(decision["should_retry"])
        self.assertIsNone(decision["idempotency_key"])
        self.assertIn("not declared idempotent", decision["reason"])

    def test_retry_policy_permits_idempotent_retry_under_ceiling(self):
        policy = RetryPolicy(max_retries=3, initial_backoff_seconds=2.0, backoff_multiplier=2.0)
        outcome = build_task_outcome(OUTCOME_TIMEOUT, 5000, "task-fetch", "attempt-1")
        payload = {"url": "https://local.test/data"}

        # Attempt 1 failed -> eligible for attempt 2
        decision = policy.evaluate(
            "task-fetch",
            outcome,
            attempt_count=1,
            is_idempotent=True,
            task_payload=payload,
        )
        self.assertTrue(decision["should_retry"])
        self.assertEqual(decision["backoff_seconds"], 4.0)
        self.assertIsNotNone(decision["idempotency_key"])
        self.assertIn("Eligible for bounded retry", decision["reason"])

        # Attempt 2 failed -> eligible for attempt 3
        decision2 = policy.evaluate(
            "task-fetch",
            outcome,
            attempt_count=2,
            is_idempotent=True,
            task_payload=payload,
        )
        self.assertTrue(decision2["should_retry"])
        self.assertEqual(decision2["backoff_seconds"], 8.0)

        # Attempt 3 failed -> reaches ceiling (3) -> blocked
        decision3 = policy.evaluate(
            "task-fetch",
            outcome,
            attempt_count=3,
            is_idempotent=True,
            task_payload=payload,
        )
        self.assertFalse(decision3["should_retry"])
        self.assertEqual(decision3["backoff_seconds"], 0.0)
        self.assertIn("ceiling", decision3["reason"])


if __name__ == "__main__":
    unittest.main()

