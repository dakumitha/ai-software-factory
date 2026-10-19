"""Smart Zero-Cost LLM Router and Multi-Provider Failover Engine.

Inspired by FreeLLMAPI (https://github.com/tashfeenahmed/freellmapi),
this module pools multiple free-tier LLM endpoints (Google Gemini, Groq, local Ollama,
and intelligent heuristic synthesizers). It tracks usage, detects rate limits (HTTP 429),
and automatically fails over to the next available free provider with zero disruption
and a strict ₹0 / $0 spend guarantee.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Any

from .agent_adapter import (
    AgentAdapterError,
    AgentBudget,
    AgentResponse,
    AutoSelectAgentAdapter,
    CodingAgentAdapter,
    GeminiFreeAgentAdapter,
    GroqFreeAgentAdapter,
    HeuristicSynthesisAdapter,
    OllamaAgentAdapter,
    QuotaExhaustedError,
)


@dataclass
class ProviderHealth:
    """Health and rate-limit tracking for a single free LLM provider."""
    provider_name: str
    is_healthy: bool = True
    consecutive_failures: int = 0
    last_failure_reason: str = ""
    last_failure_time: float = 0.0
    cooldown_seconds: float = 60.0
    total_calls: int = 0
    total_tokens: int = 0

    def mark_success(self, tokens: int) -> None:
        self.is_healthy = True
        self.consecutive_failures = 0
        self.total_calls += 1
        self.total_tokens += tokens

    def mark_failure(self, reason: str, is_rate_limit: bool = False) -> None:
        self.consecutive_failures += 1
        self.last_failure_reason = reason
        self.last_failure_time = time.time()
        # Rate limits impose cooldown; general errors back off incrementally
        self.cooldown_seconds = 120.0 if is_rate_limit else min(300.0, 30.0 * self.consecutive_failures)
        self.is_healthy = False

    def is_available(self) -> bool:
        if self.is_healthy:
            return True
        if time.time() - self.last_failure_time > self.cooldown_seconds:
            self.is_healthy = True
            return True
        return False


class FreeLlmRouter(CodingAgentAdapter):
    """Smart router pooling free LLMs with automated failover and zero-spend policy."""

    def __init__(
        self,
        providers: list[CodingAgentAdapter] | None = None,
        name: str = "smart-freellm-router",
    ):
        self._name = name
        self._health: dict[str, ProviderHealth] = {}
        self._providers: list[CodingAgentAdapter] = []

        if providers:
            for p in providers:
                self.register_provider(p)
        else:
            # Register standard free tier pool
            gemini_key = os.getenv("GEMINI_API_KEY")
            groq_key = os.getenv("GROQ_API_KEY")

            if gemini_key:
                self.register_provider(GeminiFreeAgentAdapter(api_key=gemini_key))
            if groq_key:
                self.register_provider(GroqFreeAgentAdapter(api_key=groq_key))
            self.register_provider(OllamaAgentAdapter())
            self.register_provider(HeuristicSynthesisAdapter())

    @property
    def adapter_name(self) -> str:
        return self._name

    def register_provider(self, adapter: CodingAgentAdapter) -> None:
        """Register a free provider adapter into the failover pool."""
        name = adapter.adapter_name
        self._providers.append(adapter)
        if name not in self._health:
            self._health[name] = ProviderHealth(provider_name=name)

    def get_health_status(self) -> dict[str, Any]:
        """Return the live health and availability of all pooled providers."""
        return {
            name: {
                "available": h.is_available(),
                "healthy": h.is_healthy,
                "total_calls": h.total_calls,
                "total_tokens": h.total_tokens,
                "last_failure": h.last_failure_reason,
            }
            for name, h in self._health.items()
        }

    def generate(
        self,
        prompt: str,
        context: dict[str, Any],
        budget: AgentBudget,
    ) -> AgentResponse:
        budget.check_call_allowed()

        errors: list[str] = []
        for provider in self._providers:
            name = provider.adapter_name
            health = self._health.get(name)
            if health and not health.is_available():
                continue

            try:
                resp = provider.generate(prompt, context, budget)
                if health:
                    health.mark_success(resp.tokens_used)
                resp.explanation += f" [Routed via {self._name} -> {name}]"
                return resp
            except QuotaExhaustedError as e:
                # Rate limit hit: mark cooldown and fail over to next provider
                if health:
                    health.mark_failure(str(e), is_rate_limit=True)
                errors.append(f"{name}: Rate limit / quota pause ({e})")
                continue
            except Exception as e:
                if health:
                    health.mark_failure(str(e), is_rate_limit=False)
                errors.append(f"{name}: Error ({e})")
                continue

        # If all pooled providers failed, fall back to offline heuristic synthesis
        fallback = HeuristicSynthesisAdapter(name=f"{self._name}-ultimate-fallback")
        resp = fallback.generate(prompt, context, budget)
        resp.explanation += f" [All upstream providers paused: {'; '.join(errors)}]"
        return resp

