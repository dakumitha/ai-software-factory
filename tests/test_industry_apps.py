"""Tests for Industry Application Generators (Amazon, Airbnb) and 34-Provider Keys Management."""
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

from software_factory.core import ApiHandler, Store
from software_factory.api_registry import ApiRegistry
from software_factory.specs import SpecStore, build_plan
from software_factory.universal_synthesizer import UniversalAppSynthesizer
from software_factory.octopus import GrandOctopus
from software_factory.free_router import FREE_PROVIDERS_CATALOG


class IndustryAppSynthesisTests(unittest.TestCase):
    def setUp(self):
        self.synthesizer = UniversalAppSynthesizer()
        self.swarm = GrandOctopus(synthesizer=self.synthesizer)

    def test_amazon_marketplace_synthesis(self):
        prompt = "Amazon e-commerce marketplace platform with search, catalog, slide-out cart, and 1-click checkout"
        bp = self.synthesizer.deconstruct_prompt(prompt)
        self.assertIn("Amazon", bp.category)
        self.assertIn("Customer / Shopper", bp.stakeholders)
        entity_names = [e["name"] for e in bp.entities]
        self.assertIn("ProductItem", entity_names)
        self.assertIn("CartItem", entity_names)
        self.assertIn("OrderRecord", entity_names)

        pkg = self.synthesizer.synthesize_application(prompt)
        self.assertTrue(pkg.syntax_verified)
        self.assertEqual(pkg.spend_usd, 0.0)
        self.assertIn("apps/web/src/App.tsx", pkg.files)
        self.assertIn("packages/shared/types/models.ts", pkg.files)
        self.assertIn("backend/api.ts", pkg.files)

        # Verify live interactive HTML5 preview
        html = pkg.preview_html
        self.assertIn("Echo Dot", html)
        self.assertIn("Sony WH-1000XM5", html)
        self.assertIn("amzSearchInput", html)
        self.assertIn("Prime One-Day", html)
        self.assertIn("amzCheckoutModal", html)
        self.assertIn("placeAmazonOrder", html)

    def test_airbnb_vacation_rental_synthesis(self):
        prompt = "Airbnb vacation rental platform with boutique stays, destination search, date range booking, and Superhost chat"
        bp = self.synthesizer.deconstruct_prompt(prompt)
        self.assertIn("Airbnb", bp.category)
        self.assertIn("Guest / Traveler", bp.stakeholders)
        entity_names = [e["name"] for e in bp.entities]
        self.assertIn("PropertyListing", entity_names)
        self.assertIn("Reservation", entity_names)
        self.assertIn("HostProfile", entity_names)

        pkg = self.synthesizer.synthesize_application(prompt)
        self.assertTrue(pkg.syntax_verified)
        self.assertEqual(pkg.spend_usd, 0.0)
        self.assertIn("apps/web/src/App.tsx", pkg.files)

        # Verify live interactive HTML5 preview
        html = pkg.preview_html
        self.assertIn("Malibu Oceanfront", html)
        self.assertIn("Zermatt Matterhorn", html)
        self.assertIn("abSearchInput", html)
        self.assertIn("Superhost", html)
        self.assertIn("airbnbBookingModal", html)
        self.assertIn("confirmAirbnbReservation", html)

    def test_file_by_agent_attribution_in_swarm(self):
        result = self.swarm.understand_prompt("Amazon e-commerce marketplace platform with search and checkout")
        self.assertTrue(result["understood"])
        state = self.swarm.get_swarm_state()
        feed = state["live_code_feed"]
        self.assertGreaterEqual(len(feed), 4)

        for item in feed:
            self.assertIn("filename", item)
            self.assertIn("agent_head", item)
            self.assertIn("agent_leg", item)
            self.assertIn("head_icon", item)
            self.assertIn("purpose", item)
            self.assertGreater(item["total_lines"], 0)

        # Check specific attribution
        heads = {item["filename"]: item["agent_head"] for item in feed}
        self.assertIn("Architect Octopus", heads.get("pnpm-workspace.yaml", ""))
        self.assertIn("Full-Stack Coder Octopus", heads.get("apps/web/src/App.tsx", ""))
        self.assertIn("Clean-Room Rea Octopus", heads.get("README.md", ""))


class All34ProvidersApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        db_path = str(Path(self.tmp.name) / "factory.sqlite3")
        ApiHandler.store = Store(db_path)
        ApiHandler.specs = SpecStore(ApiHandler.store)
        ApiHandler.api_registry = ApiRegistry(db_path)
        ApiHandler.build_plan = staticmethod(build_plan)
        ApiHandler.ai_provider = "auto"
        ApiHandler.provider_keys = {}
        ApiHandler.provider_urls = {}
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), ApiHandler)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2.0)
        self.tmp.cleanup()

    def request(self, path: str, method: str = "GET", payload: dict | None = None) -> tuple[int, dict]:
        url = f"http://127.0.0.1:{self.port}{path}"
        data = json.dumps(payload).encode("utf-8") if payload else None
        headers = {"Content-Type": "application/json"} if payload else {}
        req = Request(url, data=data, headers=headers, method=method)
        with urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))

    def test_get_ai_keys_returns_all_34_providers(self):
        status, data = self.request("/ai/keys")
        self.assertEqual(status, 200)
        self.assertEqual(data["total_providers"], 34)
        self.assertIn("providers", data)
        self.assertEqual(len(data["providers"]), 34)
        self.assertTrue(data["zero_spend_enforced"])

        provider_names = {p["name"] for p in data["providers"]}
        self.assertIn("DeepSeek", provider_names)
        self.assertIn("MistralAI", provider_names)
        self.assertIn("TogetherAI", provider_names)
        self.assertIn("Cloudflare", provider_names)
        self.assertIn("HuggingFace", provider_names)
        self.assertIn("GitHubModels", provider_names)
        self.assertIn("SambaNova", provider_names)
        self.assertIn("NovitaAI", provider_names)

    def test_post_ai_keys_for_all_providers_batch(self):
        payload = {
            "keys": {
                "deepseek": "mock-deepseek-key-12345678",
                "mistralai": "test-mistral-key-1234",
                "togetherai": "test-together-key-1234",
                "cloudflare": "test-cf-token-12345",
            },
            "urls": {
                "deepseek": "https://custom.deepseek.proxy/v1",
            },
            "active_provider": "deepseek",
        }
        status, data = self.request("/ai/keys", method="POST", payload=payload)
        self.assertEqual(status, 200)
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["active_provider"], "deepseek")
        self.assertGreaterEqual(data["configured_count"], 4)

        # Verify reflected in GET
        status2, data2 = self.request("/ai/keys")
        self.assertEqual(status2, 200)
        prov_map = {p["slug"]: p for p in data2["providers"]}
        self.assertTrue(prov_map["deepseek"]["configured"])
        self.assertEqual(prov_map["deepseek"]["endpoint"], "https://custom.deepseek.proxy/v1")
        self.assertTrue(prov_map["mistralai"]["configured"])
        self.assertTrue(prov_map["togetherai"]["configured"])
        self.assertTrue(prov_map["cloudflare"]["configured"])

    def test_test_connection_for_any_provider(self):
        payload = {
            "provider": "deepseek",
            "api_key": "mock-deepseek-test-key",
            "base_url": "https://api.deepseek.com/v1",
        }
        status, data = self.request("/ai/keys/test", method="POST", payload=payload)
        self.assertEqual(status, 200)
        self.assertTrue(data["connected"])
        self.assertEqual(data["provider"], "deepseek")
        self.assertTrue(data["zero_spend_verified"])


if __name__ == "__main__":
    unittest.main()
