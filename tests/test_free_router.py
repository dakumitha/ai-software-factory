"""Tests for Smart Zero-Cost LLM Router, 100+ Free Models Catalog, and Failover Engine."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from software_factory.agent_adapter import (
    AgentBudget,
    CerebrasFreeAgentAdapter,
    HeuristicSynthesisAdapter,
    OpenRouterFreeAgentAdapter,
    QuotaExhaustedError,
)
from software_factory.core import ApiHandler, Store
from software_factory.api_registry import ApiRegistry
from software_factory.specs import SpecStore, build_plan
from software_factory.free_router import (
    FREE_MODELS_CATALOG,
    FreeLlmRouter,
    ProviderHealth,
    get_free_models_catalog,
)


class FreeRouterCatalogTests(unittest.TestCase):
    def test_catalog_has_over_40_models_with_strict_zero_cost(self):
        catalog = get_free_models_catalog()
        self.assertGreaterEqual(len(catalog), 40)
        for model in catalog:
            self.assertEqual(model["cost_usd"], 0.0)
            self.assertTrue(model["zero_spend_verified"])
            self.assertIn("id", model)
            self.assertIn("name", model)
            self.assertIn("provider", model)
            self.assertIn("category", model)
            self.assertGreater(model["context_window"], 0)

    def test_catalog_contains_openrouter_free_models(self):
        openrouter_models = [m for m in FREE_MODELS_CATALOG if m.provider == "OpenRouter"]
        self.assertGreaterEqual(len(openrouter_models), 20)
        ids = {m.id for m in openrouter_models}
        self.assertIn("meta-llama/llama-3.3-70b-instruct:free", ids)
        self.assertIn("deepseek/deepseek-r1:free", ids)
        self.assertIn("qwen/qwen-2.5-coder-32b-instruct:free", ids)
        self.assertIn("google/gemini-2.0-flash-exp:free", ids)

    def test_catalog_contains_groq_cerebras_and_local(self):
        providers = {m.provider for m in FREE_MODELS_CATALOG}
        self.assertIn("Groq", providers)
        self.assertIn("Cerebras", providers)
        self.assertIn("Google", providers)
        self.assertIn("Cloudflare", providers)
        self.assertIn("HuggingFace", providers)
        self.assertIn("Ollama", providers)

    def test_provider_health_tracking_and_cooldown(self):
        health = ProviderHealth(provider_name="test-provider")
        self.assertTrue(health.is_available())
        self.assertTrue(health.is_healthy)

        # Mark failure with rate limit
        health.mark_failure("HTTP 429 Too Many Requests", is_rate_limit=True)
        self.assertFalse(health.is_available())
        self.assertFalse(health.is_healthy)
        self.assertEqual(health.consecutive_failures, 1)
        self.assertEqual(health.cooldown_seconds, 120.0)

        # Mark success resets
        health.mark_success(tokens=500)
        self.assertTrue(health.is_available())
        self.assertTrue(health.is_healthy)
        self.assertEqual(health.consecutive_failures, 0)
        self.assertEqual(health.total_calls, 1)
        self.assertEqual(health.total_tokens, 500)

    def test_free_llm_router_automatic_failover(self):
        budget = AgentBudget()

        class FailingProvider:
            adapter_name = "failing-provider"
            def generate(self, prompt, context, budget):
                raise QuotaExhaustedError("Rate limit reached (429)")

        router = FreeLlmRouter(providers=[
            FailingProvider(),
            HeuristicSynthesisAdapter(name="working-fallback"),
        ])
        resp = router.generate("Build customer dashboard", {"task_id": "cust"}, budget)
        self.assertEqual(resp.status, "COMPLETED")
        self.assertEqual(resp.cost_usd, 0.0)
        self.assertIn("working-fallback", resp.explanation)

        health_status = router.get_health_status()
        self.assertIn("failing-provider", health_status)
        self.assertFalse(health_status["failing-provider"]["healthy"])
        self.assertIn("working-fallback", health_status)
        self.assertTrue(health_status["working-fallback"]["healthy"])

    def test_router_get_catalog(self):
        router = FreeLlmRouter()
        catalog = router.get_catalog()
        self.assertGreaterEqual(len(catalog), 40)


class FreeRouterApiEndpointTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        db_path = str(Path(self.tmp.name) / "factory.sqlite3")
        ApiHandler.store = Store(db_path)
        ApiHandler.specs = SpecStore(ApiHandler.store)
        ApiHandler.api_registry = ApiRegistry(db_path)
        ApiHandler.build_plan = staticmethod(build_plan)
        ApiHandler.ai_provider = "heuristic"
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), ApiHandler)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2.0)
        self.tmp.cleanup()

    def request(self, path: str) -> tuple[int, dict]:
        req = Request(f"http://127.0.0.1:{self.port}{path}")
        with urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))

    def test_get_ai_models_endpoint(self):
        status, data = self.request("/ai/models")
        self.assertEqual(status, 200)
        self.assertTrue(data["zero_spend_enforced"])
        self.assertGreaterEqual(data["total_free_models"], 40)
        self.assertEqual(len(data["models"]), data["total_free_models"])

    def test_get_ai_config_endpoint_reports_zero_spend(self):
        status, data = self.request("/ai/config")
        self.assertEqual(status, 200)
        self.assertTrue(data["zero_spend_enforced"])
        self.assertEqual(data["spend_usd"], 0.0)
        self.assertIn("total_free_models", data)


if __name__ == "__main__":
    unittest.main()

