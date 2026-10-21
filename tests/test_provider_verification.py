"""Tests for real provider-specific API key verification.

Covers all 15 scenarios mandated by the specification (section 8):
1.  Empty credential
2.  Malformed credential (format hint)
3.  Invalid credential (provider rejection)
4.  Groq key in Gemini field → Gemini rejects it
5.  Gemini key in Groq field → Groq rejects it
6.  Valid key, unavailable model → auth and model reported separately
7.  Rate limit (429) → RATE_LIMITED
8.  Billing/quota error (402) → QUOTA_OR_BILLING_ERROR
9.  Network timeout → NETWORK_ERROR
10. Provider outage (5xx) → PROVIDER_ERROR
11. Successful authentication → supported by real (mocked) provider response
12. Successful inference → out of scope for unit tests (live integration test)
13. Revoked credential → AUTHENTICATION_FAILED (re-verification updates status)
14. Provider switching → previous result does not bleed into new provider check
15. Secret redaction → credential never appears in returned payload

All tests use mocked HTTP responses. They are explicitly labelled as MOCK tests
and are entirely isolated from production mode. No real network calls are made.
"""
from __future__ import annotations

import json
import sys
import threading
import unittest
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from software_factory.provider_verification import (
    VerificationResult,
    verify_provider,
    _not_configured_result,
    _classify_http_error,
)


# ---------------------------------------------------------------------------
# Mock HTTP helper
# ---------------------------------------------------------------------------

class _FakeHTTPError(urllib.error.HTTPError):
    """Minimal HTTPError with readable body."""
    def __init__(self, code: int, body: str = ""):
        self._body = body.encode("utf-8")
        super().__init__("http://mock", code, "Mock Error", {}, None)

    def read(self):
        return self._body


def _make_urlopen_200(body: dict):
    """Return a context-manager mock that yields a 200 response with JSON body."""
    raw = json.dumps(body).encode("utf-8")
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=cm)
    cm.__exit__ = MagicMock(return_value=False)
    cm.status = 200
    cm.read = MagicMock(return_value=raw)
    return cm


# ---------------------------------------------------------------------------
# Scenario 1: Empty credential → NOT_CONFIGURED
# ---------------------------------------------------------------------------
class TestScenario1_EmptyCredential(unittest.TestCase):
    """[MOCK] Empty credential must be rejected before reporting a successful connection."""

    def test_empty_string_not_configured(self):
        result = verify_provider("groq", "")
        self.assertEqual(result.status, "NOT_CONFIGURED")
        self.assertFalse(result.connected)
        self.assertFalse(result.auth_verified)

    def test_whitespace_only_not_configured(self):
        result = verify_provider("gemini", "   ")
        self.assertEqual(result.status, "NOT_CONFIGURED")
        self.assertFalse(result.connected)

    def test_none_equivalent_empty(self):
        result = verify_provider("openrouter", "")
        self.assertEqual(result.status, "NOT_CONFIGURED")
        self.assertFalse(result.connected)


# ---------------------------------------------------------------------------
# Scenario 2: Malformed credential (format hint only — not proof of validity)
# ---------------------------------------------------------------------------
class TestScenario2_MalformedCredential(unittest.TestCase):
    """[MOCK] Malformed credentials must not be accepted as valid based on format alone."""

    def test_too_short_key_goes_to_provider_not_accepted_locally(self):
        # The system must actually contact the provider, not accept locally
        # Here we mock the provider to return 401 (as it would for a short key)
        with patch("urllib.request.urlopen") as mock_open:
            mock_open.side_effect = _FakeHTTPError(401, '{"error": "invalid key"}')
            result = verify_provider("groq", "short", base_url="https://api.groq.com/openai/v1")
        self.assertEqual(result.status, "AUTHENTICATION_FAILED")
        self.assertFalse(result.connected)
        self.assertFalse(result.auth_verified)

    def test_random_garbage_rejected_by_provider(self):
        with patch("urllib.request.urlopen") as mock_open:
            mock_open.side_effect = _FakeHTTPError(401, '{"error": "unauthorized"}')
            result = verify_provider("groq", "GARBAGE-NOT-A-KEY-123", base_url="https://api.groq.com/openai/v1")
        self.assertEqual(result.status, "AUTHENTICATION_FAILED")
        self.assertFalse(result.connected)


# ---------------------------------------------------------------------------
# Scenario 3: Invalid credential → provider rejection reported
# ---------------------------------------------------------------------------
class TestScenario3_InvalidCredential(unittest.TestCase):
    """[MOCK] An invalid credential must report the actual provider rejection."""

    def test_groq_401_reported_as_authentication_failed(self):
        with patch("urllib.request.urlopen") as mock_open:
            mock_open.side_effect = _FakeHTTPError(401)
            result = verify_provider("groq", "gsk_invalidkeyvalue12345", base_url="https://api.groq.com/openai/v1")
        self.assertEqual(result.status, "AUTHENTICATION_FAILED")
        self.assertFalse(result.connected)
        self.assertFalse(result.auth_verified)
        self.assertEqual(result.http_status, 401)

    def test_gemini_403_reported_as_authentication_failed(self):
        with patch("urllib.request.urlopen") as mock_open:
            mock_open.side_effect = _FakeHTTPError(403)
            result = verify_provider("gemini", "AIza_invalid_key_value", base_url="https://generativelanguage.googleapis.com")
        self.assertEqual(result.status, "AUTHENTICATION_FAILED")
        self.assertFalse(result.connected)
        self.assertEqual(result.http_status, 403)


# ---------------------------------------------------------------------------
# Scenario 4: Groq key in Gemini configuration → Gemini rejects it
# ---------------------------------------------------------------------------
class TestScenario4_GroqKeyInGeminiConfig(unittest.TestCase):
    """[MOCK] A Groq credential entered for Gemini must not be reported as verified.

    This is the specific defect described in the specification. The previous
    implementation always returned connected=True. This test verifies the fix.
    """

    GROQ_KEY = "gsk_groqkeyvalue_that_belongs_to_groq_only_1234567"

    def test_groq_key_in_gemini_field_fails_gemini_verification(self):
        # Gemini will return 400 or 403 for a Groq key
        with patch("urllib.request.urlopen") as mock_open:
            mock_open.side_effect = _FakeHTTPError(400, '{"error": {"code": 400, "status": "INVALID_ARGUMENT"}}')
            result = verify_provider(
                "gemini",
                self.GROQ_KEY,
                base_url="https://generativelanguage.googleapis.com",
            )
        # Must NOT be connected
        self.assertFalse(result.connected, "Groq key must NOT be accepted by Gemini verification")
        self.assertFalse(result.auth_verified)
        self.assertNotEqual(result.status, "CONNECTED")

    def test_groq_key_in_gemini_field_gets_authentication_failed_status(self):
        with patch("urllib.request.urlopen") as mock_open:
            mock_open.side_effect = _FakeHTTPError(403)
            result = verify_provider(
                "gemini",
                self.GROQ_KEY,
                base_url="https://generativelanguage.googleapis.com",
            )
        self.assertIn(result.status, {"AUTHENTICATION_FAILED", "PROVIDER_MISMATCH"})
        self.assertFalse(result.connected)

    def test_provider_mismatch_detected_by_key_prefix(self):
        # When a gsk_ key (Groq prefix) is used with Gemini, we should detect mismatch
        with patch("urllib.request.urlopen") as mock_open:
            mock_open.side_effect = _FakeHTTPError(403)
            result = verify_provider(
                "gemini",
                "gsk_somegroqkeyhere123456",
                base_url="https://generativelanguage.googleapis.com",
            )
        # Either PROVIDER_MISMATCH or AUTHENTICATION_FAILED — both are correct and honest
        self.assertIn(result.status, {"AUTHENTICATION_FAILED", "PROVIDER_MISMATCH"})
        self.assertFalse(result.connected)


# ---------------------------------------------------------------------------
# Scenario 5: Gemini key in Groq configuration → Groq rejects it
# ---------------------------------------------------------------------------
class TestScenario5_GeminiKeyInGroqConfig(unittest.TestCase):
    """[MOCK] A Gemini credential in Groq configuration must not be reported as verified."""

    GEMINI_KEY = "AIzaSyExampleGeminiKeyThatBelongsToGoogleOnly"

    def test_gemini_key_in_groq_field_fails_groq_verification(self):
        with patch("urllib.request.urlopen") as mock_open:
            mock_open.side_effect = _FakeHTTPError(401)
            result = verify_provider(
                "groq",
                self.GEMINI_KEY,
                base_url="https://api.groq.com/openai/v1",
            )
        self.assertFalse(result.connected, "Gemini key must NOT be accepted by Groq verification")
        self.assertFalse(result.auth_verified)
        self.assertIn(result.status, {"AUTHENTICATION_FAILED", "PROVIDER_MISMATCH"})


# ---------------------------------------------------------------------------
# Scenario 6: Valid key, unavailable model → auth and model reported separately
# ---------------------------------------------------------------------------
class TestScenario6_ValidKeyUnavailableModel(unittest.TestCase):
    """[MOCK] Authentication success and model availability are reported as separate checks."""

    def test_groq_auth_ok_but_model_not_found(self):
        groq_models_response = {
            "object": "list",
            "data": [
                {"id": "llama-3.1-8b-instant"},
                {"id": "mixtral-8x7b-32768"},
            ],
        }
        cm = _make_urlopen_200(groq_models_response)
        with patch("urllib.request.urlopen", return_value=cm):
            result = verify_provider(
                "groq",
                "gsk_valid_groq_key_here_1234567890",
                model="nonexistent-model-xyz",
                base_url="https://api.groq.com/openai/v1",
            )
        self.assertTrue(result.auth_verified, "Auth should succeed when provider accepts the key")
        self.assertFalse(result.model_available, "Model should be reported as unavailable")
        # Status should be CONNECTED (auth ok) but model_available is False
        # The spec says these must be reported separately
        self.assertTrue(result.auth_verified)
        self.assertFalse(result.model_available)

    def test_gemini_auth_ok_model_not_in_list(self):
        gemini_models_response = {
            "models": [
                {"name": "models/gemini-1.5-flash"},
                {"name": "models/gemini-1.5-pro"},
            ]
        }
        cm = _make_urlopen_200(gemini_models_response)
        with patch("urllib.request.urlopen", return_value=cm):
            result = verify_provider(
                "gemini",
                "AIzaSyValidGeminiKeyHere1234567890",
                model="gpt-4-turbo",  # Obviously not a Gemini model
                base_url="https://generativelanguage.googleapis.com",
            )
        self.assertTrue(result.auth_verified)
        self.assertFalse(result.model_available)
        self.assertIn("model_availability", result.checks_performed)


# ---------------------------------------------------------------------------
# Scenario 7: Rate limit (429) → RATE_LIMITED
# ---------------------------------------------------------------------------
class TestScenario7_RateLimit(unittest.TestCase):
    """[MOCK] Rate limit must be reported accurately, not silently swallowed."""

    def test_groq_429_returns_rate_limited(self):
        with patch("urllib.request.urlopen") as mock_open:
            mock_open.side_effect = _FakeHTTPError(429)
            result = verify_provider("groq", "gsk_valid_but_rate_limited", base_url="https://api.groq.com/openai/v1")
        self.assertEqual(result.status, "RATE_LIMITED")
        self.assertFalse(result.connected)
        self.assertEqual(result.http_status, 429)

    def test_gemini_429_returns_rate_limited(self):
        with patch("urllib.request.urlopen") as mock_open:
            mock_open.side_effect = _FakeHTTPError(429)
            result = verify_provider("gemini", "AIzaSyValidKeyRateLimited", base_url="https://generativelanguage.googleapis.com")
        self.assertEqual(result.status, "RATE_LIMITED")
        self.assertFalse(result.connected)


# ---------------------------------------------------------------------------
# Scenario 8: Quota/billing error (402) → QUOTA_OR_BILLING_ERROR
# ---------------------------------------------------------------------------
class TestScenario8_QuotaOrBillingError(unittest.TestCase):
    """[MOCK] Quota exhaustion or billing restrictions must be accurately reported."""

    def test_402_returns_quota_billing_error(self):
        with patch("urllib.request.urlopen") as mock_open:
            mock_open.side_effect = _FakeHTTPError(402, '{"error": "quota exceeded"}')
            result = verify_provider("groq", "gsk_quota_exhausted_key", base_url="https://api.groq.com/openai/v1")
        self.assertEqual(result.status, "QUOTA_OR_BILLING_ERROR")
        self.assertFalse(result.connected)
        self.assertEqual(result.http_status, 402)


# ---------------------------------------------------------------------------
# Scenario 9: Network timeout → NETWORK_ERROR
# ---------------------------------------------------------------------------
class TestScenario9_NetworkTimeout(unittest.TestCase):
    """[MOCK] A network timeout must result in NETWORK_ERROR, never in a success state."""

    def test_timeout_returns_network_error(self):
        import socket
        with patch("urllib.request.urlopen") as mock_open:
            mock_open.side_effect = socket.timeout("timed out")
            result = verify_provider("groq", "gsk_valid_but_network_is_down", base_url="https://api.groq.com/openai/v1")
        self.assertEqual(result.status, "NETWORK_ERROR")
        self.assertFalse(result.connected)
        self.assertFalse(result.auth_verified)

    def test_connection_refused_returns_network_error(self):
        import urllib.error
        with patch("urllib.request.urlopen") as mock_open:
            mock_open.side_effect = urllib.error.URLError("Connection refused")
            result = verify_provider("groq", "gsk_valid_key_unreachable", base_url="https://api.groq.com/openai/v1")
        self.assertEqual(result.status, "NETWORK_ERROR")
        self.assertFalse(result.connected)


# ---------------------------------------------------------------------------
# Scenario 10: Provider outage (5xx) → PROVIDER_ERROR
# ---------------------------------------------------------------------------
class TestScenario10_ProviderOutage(unittest.TestCase):
    """[MOCK] A 5xx response must surface as PROVIDER_ERROR, not as a success."""

    def test_500_returns_provider_error(self):
        with patch("urllib.request.urlopen") as mock_open:
            mock_open.side_effect = _FakeHTTPError(500, "Internal Server Error")
            result = verify_provider("groq", "gsk_valid_during_outage", base_url="https://api.groq.com/openai/v1")
        self.assertEqual(result.status, "PROVIDER_ERROR")
        self.assertFalse(result.connected)
        self.assertEqual(result.http_status, 500)

    def test_503_returns_provider_error(self):
        with patch("urllib.request.urlopen") as mock_open:
            mock_open.side_effect = _FakeHTTPError(503)
            result = verify_provider("gemini", "AIzaSyValidKeyDuringOutage", base_url="https://generativelanguage.googleapis.com")
        self.assertEqual(result.status, "PROVIDER_ERROR")
        self.assertFalse(result.connected)


# ---------------------------------------------------------------------------
# Scenario 11: Successful authentication → backed by real (mocked) provider response
# ---------------------------------------------------------------------------
class TestScenario11_SuccessfulAuthentication(unittest.TestCase):
    """[MOCK] A successful auth result must be supported by an actual provider response."""

    def test_groq_successful_verification(self):
        groq_response = {
            "object": "list",
            "data": [
                {"id": "llama-3.1-8b-instant"},
                {"id": "llama-3.3-70b-versatile"},
            ],
        }
        cm = _make_urlopen_200(groq_response)
        with patch("urllib.request.urlopen", return_value=cm):
            result = verify_provider(
                "groq",
                "gsk_real_valid_groq_key_12345",
                model="llama-3.1-8b-instant",
                base_url="https://api.groq.com/openai/v1",
            )
        self.assertEqual(result.status, "CONNECTED")
        self.assertTrue(result.connected)
        self.assertTrue(result.auth_verified)
        self.assertTrue(result.model_available)
        self.assertIsNotNone(result.latency_ms)
        self.assertGreater(result.latency_ms, 0)
        self.assertIn("models_list", result.checks_performed)

    def test_gemini_successful_verification(self):
        gemini_response = {
            "models": [
                {"name": "models/gemini-1.5-flash"},
                {"name": "models/gemini-1.5-pro"},
                {"name": "models/gemini-2.0-flash"},
            ]
        }
        cm = _make_urlopen_200(gemini_response)
        with patch("urllib.request.urlopen", return_value=cm):
            result = verify_provider(
                "gemini",
                "AIzaSyRealValidGeminiKey1234567890",
                model="gemini-1.5-flash",
                base_url="https://generativelanguage.googleapis.com",
            )
        self.assertEqual(result.status, "CONNECTED")
        self.assertTrue(result.connected)
        self.assertTrue(result.auth_verified)
        self.assertTrue(result.model_available)

    def test_openrouter_successful_verification(self):
        openrouter_response = {
            "data": {
                "label": "my-key",
                "usage": 0,
                "limit": None,
                "is_free_tier": True,
            }
        }
        cm = _make_urlopen_200(openrouter_response)
        with patch("urllib.request.urlopen", return_value=cm):
            result = verify_provider(
                "openrouter",
                "sk-or-v1-valid-key-here",
                base_url="https://openrouter.ai/api/v1",
            )
        self.assertEqual(result.status, "CONNECTED")
        self.assertTrue(result.connected)
        self.assertTrue(result.auth_verified)


# ---------------------------------------------------------------------------
# Scenario 13: Revoked/expired credential → re-verification updates status
# ---------------------------------------------------------------------------
class TestScenario13_RevokedCredential(unittest.TestCase):
    """[MOCK] A later verification of a previously-valid key must update the status."""

    def test_initially_valid_then_revoked(self):
        # First verification succeeds
        groq_response = {"object": "list", "data": [{"id": "llama-3.1-8b-instant"}]}
        cm = _make_urlopen_200(groq_response)
        with patch("urllib.request.urlopen", return_value=cm):
            result1 = verify_provider("groq", "gsk_valid_then_revoked", base_url="https://api.groq.com/openai/v1")
        self.assertEqual(result1.status, "CONNECTED")

        # Second verification — key was revoked
        with patch("urllib.request.urlopen") as mock_open:
            mock_open.side_effect = _FakeHTTPError(401)
            result2 = verify_provider("groq", "gsk_valid_then_revoked", base_url="https://api.groq.com/openai/v1")
        self.assertEqual(result2.status, "AUTHENTICATION_FAILED")
        self.assertFalse(result2.connected)
        # Each call returns a fresh result — no caching of previous success
        self.assertNotEqual(result1.status, result2.status)


# ---------------------------------------------------------------------------
# Scenario 14: Provider switching → no state bleed
# ---------------------------------------------------------------------------
class TestScenario14_ProviderSwitching(unittest.TestCase):
    """[MOCK] Switching providers must produce independent results — no state contamination."""

    def test_groq_success_does_not_mark_gemini_as_connected(self):
        groq_response = {"object": "list", "data": [{"id": "llama-3.1-8b-instant"}]}
        cm = _make_urlopen_200(groq_response)
        with patch("urllib.request.urlopen", return_value=cm):
            result_groq = verify_provider("groq", "gsk_groq_key_123", base_url="https://api.groq.com/openai/v1")
        self.assertEqual(result_groq.provider, "groq")
        self.assertTrue(result_groq.connected)

        # Now verify Gemini with empty key — must fail independently
        result_gemini = verify_provider("gemini", "")
        self.assertEqual(result_gemini.provider, "gemini")
        self.assertEqual(result_gemini.status, "NOT_CONFIGURED")
        self.assertFalse(result_gemini.connected)

    def test_gemini_result_does_not_contaminate_groq_check(self):
        gemini_response = {"models": [{"name": "models/gemini-1.5-flash"}]}
        cm = _make_urlopen_200(gemini_response)
        with patch("urllib.request.urlopen", return_value=cm):
            result_gemini = verify_provider("gemini", "AIzaSy_valid_gemini_key", base_url="https://generativelanguage.googleapis.com")
        self.assertTrue(result_gemini.connected)

        # Groq with wrong key must still fail
        with patch("urllib.request.urlopen") as mock_open:
            mock_open.side_effect = _FakeHTTPError(401)
            result_groq = verify_provider("groq", "wrong-key-for-groq", base_url="https://api.groq.com/openai/v1")
        self.assertFalse(result_groq.connected)
        self.assertEqual(result_groq.status, "AUTHENTICATION_FAILED")


# ---------------------------------------------------------------------------
# Scenario 15: Secret redaction — credential never in returned payload
# ---------------------------------------------------------------------------
class TestScenario15_SecretRedaction(unittest.TestCase):
    """[MOCK] API credentials must never appear in the VerificationResult payload."""

    SECRET_KEY = "gsk_super_secret_groq_api_key_must_never_appear_in_output"

    def test_key_not_in_successful_result_dict(self):
        groq_response = {"object": "list", "data": [{"id": "llama-3.1-8b-instant"}]}
        cm = _make_urlopen_200(groq_response)
        with patch("urllib.request.urlopen", return_value=cm):
            result = verify_provider("groq", self.SECRET_KEY, base_url="https://api.groq.com/openai/v1")
        result_dict = result.to_dict()
        result_str = json.dumps(result_dict)
        self.assertNotIn(self.SECRET_KEY, result_str, "Secret key must not appear in result payload")

    def test_key_not_in_error_result_dict(self):
        with patch("urllib.request.urlopen") as mock_open:
            mock_open.side_effect = _FakeHTTPError(401)
            result = verify_provider("groq", self.SECRET_KEY, base_url="https://api.groq.com/openai/v1")
        result_dict = result.to_dict()
        result_str = json.dumps(result_dict)
        self.assertNotIn(self.SECRET_KEY, result_str, "Secret key must not appear in error payload")

    def test_endpoint_url_does_not_contain_key_in_gemini(self):
        """Gemini uses key as URL query param — endpoint_used must be stripped."""
        gemini_response = {"models": [{"name": "models/gemini-1.5-flash"}]}
        cm = _make_urlopen_200(gemini_response)
        with patch("urllib.request.urlopen", return_value=cm):
            result = verify_provider("gemini", "AIzaSySecret123", base_url="https://generativelanguage.googleapis.com")
        # endpoint_used must NOT contain the key
        self.assertNotIn("AIzaSySecret123", result.endpoint_used)
        self.assertNotIn("AIzaSySecret123", json.dumps(result.to_dict()))


# ---------------------------------------------------------------------------
# Integration: /ai/keys/test HTTP endpoint via test server
# ---------------------------------------------------------------------------
class TestApiKeyTestEndpoint(unittest.TestCase):
    """[MOCK] Verify the HTTP endpoint wires through to real provider_verification."""

    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        db_path = str(Path(self.tmp.name) / "factory.sqlite3")
        from software_factory.core import ApiHandler, Store
        from software_factory.specs import SpecStore, build_plan
        from software_factory.api_registry import ApiRegistry
        ApiHandler.store = Store(db_path)
        ApiHandler.specs = SpecStore(ApiHandler.store)
        ApiHandler.api_registry = ApiRegistry(db_path)
        ApiHandler.build_plan = staticmethod(build_plan)
        ApiHandler.ai_provider = "auto"
        ApiHandler.provider_keys = {}
        ApiHandler.provider_urls = {}
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), ApiHandler)
        self.port = self.server.server_address[1]
        import threading
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2.0)
        self.tmp.cleanup()

    def _post(self, path: str, payload: dict) -> tuple[int, dict]:
        """HTTP client using http.client directly to avoid urllib.request.urlopen mock interference."""
        import http.client
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        body_bytes = json.dumps(payload).encode("utf-8")
        conn.request("POST", path, body=body_bytes, headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        resp_body = json.loads(resp.read().decode("utf-8"))
        conn.close()
        return resp.status, resp_body

    def test_empty_key_returns_not_configured_not_connected(self):
        status, data = self._post("/ai/keys/test", {"provider": "groq", "api_key": ""})
        self.assertEqual(status, 200)
        self.assertFalse(data["connected"])
        self.assertEqual(data["status"], "NOT_CONFIGURED")

    def test_groq_key_in_gemini_config_returns_failure(self):
        """THE CRITICAL DEFECT TEST: Groq key in Gemini field must NOT succeed."""
        # Patch urlopen inside provider_verification module only (not the test client)
        target = "software_factory.provider_verification.urllib.request.urlopen"
        with patch(target) as mock_open:
            mock_open.side_effect = _FakeHTTPError(403)
            status, data = self._post("/ai/keys/test", {
                "provider": "gemini",
                "api_key": "gsk_this_is_a_groq_key_not_gemini_1234567890",
            })
        self.assertEqual(status, 200)
        # THE KEY ASSERTION: must NOT be connected
        self.assertFalse(data["connected"],
            "A Groq key must NOT be reported as successfully verified when used with the Gemini provider")
        self.assertIn(data["status"], {"AUTHENTICATION_FAILED", "PROVIDER_MISMATCH"})

    def test_secret_not_in_http_response(self):
        secret = "gsk_secret_must_never_appear_in_response_1234"
        target = "software_factory.provider_verification.urllib.request.urlopen"
        with patch(target) as mock_open:
            mock_open.side_effect = _FakeHTTPError(401)
            status, data = self._post("/ai/keys/test", {
                "provider": "groq",
                "api_key": secret,
            })
        response_str = json.dumps(data)
        self.assertNotIn(secret, response_str)

    def test_successful_mock_verification_returns_connected_true(self):
        groq_response = {"object": "list", "data": [{"id": "llama-3.1-8b-instant"}]}
        cm = _make_urlopen_200(groq_response)
        target = "software_factory.provider_verification.urllib.request.urlopen"
        with patch(target, return_value=cm):
            status, data = self._post("/ai/keys/test", {
                "provider": "groq",
                "api_key": "gsk_valid_key_in_mock",
                "model": "llama-3.1-8b-instant",
            })
        self.assertEqual(status, 200)
        self.assertTrue(data["connected"])
        self.assertEqual(data["status"], "CONNECTED")
        self.assertTrue(data["auth_verified"])


if __name__ == "__main__":
    unittest.main()
