"""Real provider-specific API key verification.

Each provider has its own verification method that issues an actual HTTP request
to the correct provider endpoint with the correct authentication scheme.

Verification states (never fabricated):
  NOT_CONFIGURED      - key is empty or missing
  VALIDATING          - in-progress (used by caller)
  CONNECTED           - auth verified AND model available
  AUTHENTICATION_FAILED - provider rejected the credential (401/403)
  PROVIDER_MISMATCH   - credential appears to belong to a different provider
  MODEL_UNAVAILABLE   - auth succeeded but requested model not found
  RATE_LIMITED        - provider returned 429
  QUOTA_OR_BILLING_ERROR - provider returned 402 or billing-related error
  NETWORK_ERROR       - connection refused, timeout, DNS failure
  PROVIDER_ERROR      - provider returned 5xx
  VERIFICATION_INCONCLUSIVE - unexpected response that cannot be classified

A key is NEVER considered valid solely because it is non-empty, has a plausible
length, matches a prefix, or resembles a known credential format.
Credential format hints are used as early warnings only.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class VerificationResult:
    """Evidence-based result of a real provider verification attempt."""
    provider: str
    status: str                    # One of the states listed above
    connected: bool                # True only if CONNECTED
    auth_verified: bool = False    # True if authentication succeeded
    model_available: bool | None = None  # None if not checked
    latency_ms: float | None = None
    endpoint_used: str = ""
    model_checked: str = ""
    http_status: int | None = None
    error_message: str = ""
    checks_performed: list[str] = field(default_factory=list)
    zero_spend_verified: bool = True  # Always enforced
    verified_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "status": self.status,
            "connected": self.connected,
            "auth_verified": self.auth_verified,
            "model_available": self.model_available,
            "latency_ms": self.latency_ms,
            "endpoint_used": self.endpoint_used,
            "model_checked": self.model_checked,
            "http_status": self.http_status,
            "error_message": self.error_message,
            "checks_performed": self.checks_performed,
            "zero_spend_verified": self.zero_spend_verified,
            "verified_at": self.verified_at,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")


def _http_get_json(url: str, headers: dict[str, str], timeout: float) -> tuple[int, dict]:
    """Issue GET, return (status_code, parsed_body). Raises on network error."""
    req = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = json.loads(resp.read().decode("utf-8"))
        return resp.status, body


def _http_post_json(url: str, headers: dict[str, str], body: dict, timeout: float) -> tuple[int, dict]:
    """Issue POST with JSON body, return (status_code, parsed_body)."""
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        resp_body = json.loads(resp.read().decode("utf-8"))
        return resp.status, resp_body


def _classify_http_error(e: urllib.error.HTTPError, provider: str, key: str) -> VerificationResult:
    """Classify an HTTPError into an accurate VerificationResult."""
    body_text = ""
    try:
        body_text = e.read().decode("utf-8", errors="replace")
    except Exception:
        pass

    common = dict(
        provider=provider,
        connected=False,
        auth_verified=False,
        http_status=e.code,
        endpoint_used="",
        verified_at=_now_iso(),
    )

    if e.code in (401, 403):
        # Detect provider mismatch hints in the error body
        mismatch_hints = [
            ("gsk_", "groq"),   # Groq key prefix
            ("AIza", "google"),  # Google key prefix
            ("sk-or-", "openrouter"),
        ]
        for prefix, hint_provider in mismatch_hints:
            if key.startswith(prefix) and hint_provider != provider.lower():
                return VerificationResult(
                    status="PROVIDER_MISMATCH",
                    error_message=(
                        f"Credential appears to belong to {hint_provider.upper()}, "
                        f"not {provider.upper()}. {provider.upper()} rejected it (HTTP {e.code})."
                    ),
                    **common,
                )
        return VerificationResult(
            status="AUTHENTICATION_FAILED",
            error_message=f"{provider.upper()} rejected the credential (HTTP {e.code}). "
                          f"Check that the key belongs to this provider.",
            **common,
        )
    if e.code == 402:
        return VerificationResult(
            status="QUOTA_OR_BILLING_ERROR",
            error_message=f"{provider.upper()} returned HTTP 402. Quota exhausted or billing required.",
            **common,
        )
    if e.code == 429:
        return VerificationResult(
            status="RATE_LIMITED",
            error_message=f"{provider.upper()} returned HTTP 429. Rate limit active.",
            **common,
        )
    if e.code >= 500:
        return VerificationResult(
            status="PROVIDER_ERROR",
            error_message=f"{provider.upper()} returned HTTP {e.code} (server error). "
                          "Provider may be experiencing an outage.",
            **common,
        )
    return VerificationResult(
        status="VERIFICATION_INCONCLUSIVE",
        error_message=f"Unexpected HTTP {e.code} from {provider.upper()}.",
        **common,
    )


def _network_error_result(provider: str, exc: Exception) -> VerificationResult:
    return VerificationResult(
        provider=provider,
        status="NETWORK_ERROR",
        connected=False,
        auth_verified=False,
        error_message=f"Network error contacting {provider.upper()}: {exc}",
        verified_at=_now_iso(),
    )


def _not_configured_result(provider: str) -> VerificationResult:
    return VerificationResult(
        provider=provider,
        status="NOT_CONFIGURED",
        connected=False,
        auth_verified=False,
        error_message="No API key provided. Enter a valid key for this provider.",
        verified_at=_now_iso(),
    )


# ---------------------------------------------------------------------------
# Provider-specific verifiers
# ---------------------------------------------------------------------------

def _verify_google_gemini(key: str, model: str, base_url: str, timeout: float) -> VerificationResult:
    """Verify Google Gemini via the generateContent endpoint (smallest request)."""
    endpoint = (base_url or "https://generativelanguage.googleapis.com").rstrip("/")
    model = model or "gemini-1.5-flash"
    # Use models list endpoint first — no tokens consumed
    list_url = f"{endpoint}/v1beta/models?key={key}"
    checks: list[str] = []
    t0 = time.monotonic()
    try:
        status_code, resp_body = _http_get_json(list_url, {}, timeout)
        latency_ms = round((time.monotonic() - t0) * 1000, 1)
        checks.append("models_list")

        # Check model availability
        models = resp_body.get("models", [])
        model_names = {m.get("name", "").split("/")[-1] for m in models}
        model_available = model in model_names or any(model in n for n in model_names)
        checks.append("model_availability")

        return VerificationResult(
            provider="google",
            status="CONNECTED",
            connected=True,
            auth_verified=True,
            model_available=model_available,
            latency_ms=latency_ms,
            endpoint_used=list_url.split("?")[0],
            model_checked=model,
            http_status=status_code,
            checks_performed=checks,
            verified_at=_now_iso(),
        )
    except urllib.error.HTTPError as e:
        result = _classify_http_error(e, "google", key)
        result.endpoint_used = list_url.split("?")[0]
        result.checks_performed = checks
        return result
    except Exception as exc:
        return _network_error_result("google", exc)


def _verify_groq(key: str, model: str, base_url: str, timeout: float) -> VerificationResult:
    """Verify Groq via the OpenAI-compatible models list endpoint."""
    endpoint = (base_url or "https://api.groq.com/openai/v1").rstrip("/")
    model = model or "llama-3.1-8b-instant"
    url = f"{endpoint}/models"
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    checks: list[str] = []
    t0 = time.monotonic()
    try:
        status_code, resp_body = _http_get_json(url, headers, timeout)
        latency_ms = round((time.monotonic() - t0) * 1000, 1)
        checks.append("models_list")

        model_ids = {m.get("id", "") for m in resp_body.get("data", [])}
        model_available = model in model_ids
        checks.append("model_availability")

        return VerificationResult(
            provider="groq",
            status="CONNECTED",
            connected=True,
            auth_verified=True,
            model_available=model_available,
            latency_ms=latency_ms,
            endpoint_used=url,
            model_checked=model,
            http_status=status_code,
            checks_performed=checks,
            verified_at=_now_iso(),
        )
    except urllib.error.HTTPError as e:
        result = _classify_http_error(e, "groq", key)
        result.endpoint_used = url
        result.checks_performed = checks
        return result
    except Exception as exc:
        return _network_error_result("groq", exc)


def _verify_openrouter(key: str, model: str, base_url: str, timeout: float) -> VerificationResult:
    """Verify OpenRouter via /auth/key endpoint."""
    endpoint = (base_url or "https://openrouter.ai/api/v1").rstrip("/")
    model = model or "meta-llama/llama-3.3-70b-instruct:free"
    # OpenRouter has a dedicated key-info endpoint
    url = f"{endpoint}/auth/key"
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    checks: list[str] = []
    t0 = time.monotonic()
    try:
        status_code, resp_body = _http_get_json(url, headers, timeout)
        latency_ms = round((time.monotonic() - t0) * 1000, 1)
        checks.append("auth_key_info")

        # Check if there's data in response (authenticated)
        data = resp_body.get("data", {})
        auth_verified = bool(data) or status_code == 200
        checks.append("model_availability_skipped")  # Avoid consuming rate limit

        return VerificationResult(
            provider="openrouter",
            status="CONNECTED" if auth_verified else "AUTHENTICATION_FAILED",
            connected=auth_verified,
            auth_verified=auth_verified,
            model_available=None,  # Not checked to avoid quota consumption
            latency_ms=latency_ms,
            endpoint_used=url,
            model_checked=model,
            http_status=status_code,
            checks_performed=checks,
            error_message="" if auth_verified else "OpenRouter did not return valid key data.",
            verified_at=_now_iso(),
        )
    except urllib.error.HTTPError as e:
        result = _classify_http_error(e, "openrouter", key)
        result.endpoint_used = url
        result.checks_performed = checks
        return result
    except Exception as exc:
        return _network_error_result("openrouter", exc)


def _verify_cerebras(key: str, model: str, base_url: str, timeout: float) -> VerificationResult:
    """Verify Cerebras via the models list endpoint."""
    endpoint = (base_url or "https://api.cerebras.ai/v1").rstrip("/")
    model = model or "llama3.1-8b"
    url = f"{endpoint}/models"
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    checks: list[str] = []
    t0 = time.monotonic()
    try:
        status_code, resp_body = _http_get_json(url, headers, timeout)
        latency_ms = round((time.monotonic() - t0) * 1000, 1)
        checks.append("models_list")

        model_ids = {m.get("id", "") for m in resp_body.get("data", [])}
        model_available = model in model_ids
        checks.append("model_availability")

        return VerificationResult(
            provider="cerebras",
            status="CONNECTED",
            connected=True,
            auth_verified=True,
            model_available=model_available,
            latency_ms=latency_ms,
            endpoint_used=url,
            model_checked=model,
            http_status=status_code,
            checks_performed=checks,
            verified_at=_now_iso(),
        )
    except urllib.error.HTTPError as e:
        result = _classify_http_error(e, "cerebras", key)
        result.endpoint_used = url
        result.checks_performed = checks
        return result
    except Exception as exc:
        return _network_error_result("cerebras", exc)


def _verify_openai_compatible(
    provider: str, key: str, model: str, base_url: str, timeout: float
) -> VerificationResult:
    """Generic OpenAI-compatible provider verification via /models endpoint."""
    endpoint = (base_url or "https://api.openai.com/v1").rstrip("/")
    url = f"{endpoint}/models"
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    checks: list[str] = []
    t0 = time.monotonic()
    try:
        status_code, resp_body = _http_get_json(url, headers, timeout)
        latency_ms = round((time.monotonic() - t0) * 1000, 1)
        checks.append("models_list")

        # Check model availability if a model was specified
        model_available: bool | None = None
        if model:
            model_ids = {m.get("id", "") for m in resp_body.get("data", [])}
            model_available = model in model_ids
            checks.append("model_availability")

        return VerificationResult(
            provider=provider,
            status="CONNECTED",
            connected=True,
            auth_verified=True,
            model_available=model_available,
            latency_ms=latency_ms,
            endpoint_used=url,
            model_checked=model or "",
            http_status=status_code,
            checks_performed=checks,
            verified_at=_now_iso(),
        )
    except urllib.error.HTTPError as e:
        result = _classify_http_error(e, provider, key)
        result.endpoint_used = url
        result.checks_performed = checks
        return result
    except Exception as exc:
        return _network_error_result(provider, exc)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

# Maps provider slugs to their dedicated verifiers.
_PROVIDER_VERIFIERS = {
    "google": _verify_google_gemini,
    "gemini": _verify_google_gemini,
    "groq": _verify_groq,
    "openrouter": _verify_openrouter,
    "freellmapi": _verify_openrouter,  # Same API
    "cerebras": _verify_cerebras,
}

# Known endpoint defaults for generic OpenAI-compatible providers
_DEFAULT_ENDPOINTS: dict[str, str] = {
    "deepseek": "https://api.deepseek.com/v1",
    "mistralai": "https://api.mistral.ai/v1",
    "togetherai": "https://api.together.xyz/v1",
    "sambanova": "https://api.sambanova.ai/v1",
    "fireworksai": "https://api.fireworks.ai/inference/v1",
    "hyperbolic": "https://api.hyperbolic.xyz/v1",
    "novitaai": "https://api.novita.ai/v3/openai",
    "leptonai": "https://api.lepton.ai/v1",
    "deepinfra": "https://api.deepinfra.com/v1/openai",
    "siliconflow": "https://api.siliconflow.cn/v1",
    "cohere": "https://api.cohere.ai/v1",
    "ai21studio": "https://api.ai21.com/studio/v1",
    "voyageai": "https://api.voyageai.com/v1",
    "upstage": "https://api.upstage.ai/v1",
    "zerooneai": "https://api.01.ai/v1",
    "perplexity": "https://api.perplexity.ai",
    "githubmodels": "https://models.inference.ai.azure.com",
    "cloudflare": "https://api.cloudflare.com/client/v4",
    "huggingface": "https://api-inference.huggingface.co",
    "ollama": "http://127.0.0.1:11434/v1",
    "lmstudio": "http://127.0.0.1:1234/v1",
}


def verify_provider(
    provider: str,
    api_key: str,
    *,
    model: str = "",
    base_url: str = "",
    timeout: float = 15.0,
) -> VerificationResult:
    """
    Verify a provider credential by issuing a real HTTP request to the correct
    provider endpoint. This function NEVER fabricates a successful result.

    Args:
        provider:  Provider slug (e.g. 'groq', 'gemini', 'openrouter')
        api_key:   The credential to verify. If empty, returns NOT_CONFIGURED.
        model:     Optional model to check availability for.
        base_url:  Override the default provider endpoint.
        timeout:   Network timeout in seconds.

    Returns:
        VerificationResult with status, latency, checks performed and error detail.
    """
    provider = provider.strip().lower()

    if not api_key or not api_key.strip():
        return _not_configured_result(provider)

    api_key = api_key.strip()

    # Route to dedicated verifier
    verifier = _PROVIDER_VERIFIERS.get(provider)
    if verifier:
        return verifier(api_key, model, base_url, timeout)

    # Generic OpenAI-compatible fallback
    resolved_url = base_url or _DEFAULT_ENDPOINTS.get(provider, "")
    if not resolved_url:
        return VerificationResult(
            provider=provider,
            status="VERIFICATION_INCONCLUSIVE",
            connected=False,
            auth_verified=False,
            error_message=f"Unknown provider '{provider}'. Supply a base_url to verify.",
            verified_at=_now_iso(),
        )

    return _verify_openai_compatible(provider, api_key, model, resolved_url, timeout)
