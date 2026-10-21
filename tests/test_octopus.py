"""Tests for the Nested Octopus Swarm Architecture and OpenAI-compatible endpoints."""
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
from software_factory.octopus import GrandOctopus, get_global_octopus_swarm
from software_factory.free_router import FREE_PROVIDERS_CATALOG, FREE_MODELS_CATALOG


class OctopusSwarmUnitTests(unittest.TestCase):
    def setUp(self):
        self.swarm = GrandOctopus()

    def test_initial_state_has_6_heads_and_12_legs(self):
        state = self.swarm.get_swarm_state()
        self.assertEqual(len(state["heads"]), 6)
        total_legs = sum(len(h["legs"]) for h in state["heads"])
        self.assertEqual(total_legs, 12)
        self.assertEqual(state["grand_head"]["state"], "READY")
        self.assertEqual(state["providers_summary"]["total_providers"], 34)
        self.assertEqual(state["providers_summary"]["total_models"], 635)
        self.assertTrue(state["providers_summary"]["zero_spend_guaranteed"])

    def test_vague_input_triggers_clarification_questions(self):
        result = self.swarm.understand_prompt("make an app")
        self.assertFalse(result["understood"])
        self.assertTrue(result["needs_clarification"])
        self.assertIn("questions", result)
        self.assertGreaterEqual(len(result["questions"]), 1)
        self.assertEqual(self.swarm.state, "INTERVIEWING")

    def test_concrete_input_dispatches_mission_and_synthesizes(self):
        result = self.swarm.understand_prompt("Calculator with scientific operations and history")
        self.assertTrue(result["understood"])
        self.assertFalse(result["needs_clarification"])
        self.assertEqual(result["overall_progress"], 100)
        self.assertEqual(result["state"], "COMPLETED")
        self.assertIn("preview_url", result)

        # Verify all heads reached completed state
        state = self.swarm.get_swarm_state()
        for head in state["heads"]:
            self.assertEqual(head["state"], "COMPLETED")
            self.assertEqual(head["progress"], 100)

    def test_inter_head_relay_records_message(self):
        msg = self.swarm.relay_inter_head("head_security", "head_coder", "Vulnerability scan passed: 0 CVE findings.")
        self.assertEqual(msg.sender_id, "head_security")
        self.assertEqual(msg.receiver_id, "head_coder")
        self.assertIn("0 CVE findings", msg.content)

        state = self.swarm.get_swarm_state()
        found = any("0 CVE findings" in m["content"] for m in state["messages"])
        self.assertTrue(found)

    def test_bookstore_synthesis_and_preview(self):
        result = self.swarm.understand_prompt("website with frontend and backend for book selling")
        self.assertTrue(result["understood"])
        self.assertFalse(result["needs_clarification"])
        self.assertIn("preview_url", result)
        pkg = self.swarm.synthesizer.synthesize_application("website with frontend and backend for book selling")
        self.assertIn("Designing Data-Intensive Applications", pkg.preview_html)
        self.assertIn("Razorpay Payment Gateway", pkg.preview_html)
        self.assertIn("Bookstore Inventory Manager", pkg.preview_html)

    def test_live_feeds_populated_in_swarm_state(self):
        self.swarm.understand_prompt("Bookstore application with online cart and checkout")
        state = self.swarm.get_swarm_state()
        self.assertGreaterEqual(len(state["live_code_feed"]), 3)
        self.assertGreaterEqual(len(state["live_security_feed"]), 3)
        self.assertGreaterEqual(len(state["live_test_feed"]), 3)
        self.assertIn("mcp_tools", state)
        self.assertEqual(len(state["mcp_tools"]), 5)


class OctopusSwarmApiTests(unittest.TestCase):
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

    def request(self, path: str, method: str = "GET", payload: dict | None = None) -> tuple[int, dict]:
        url = f"http://127.0.0.1:{self.port}{path}"
        data = json.dumps(payload).encode("utf-8") if payload else None
        headers = {"Content-Type": "application/json"} if payload else {}
        req = Request(url, data=data, headers=headers, method=method)
        with urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))

    def test_get_v1_models_endpoint_returns_635_models(self):
        status, data = self.request("/v1/models")
        self.assertEqual(status, 200)
        self.assertEqual(data["object"], "list")
        self.assertEqual(len(data["data"]), 635)

    def test_get_v1_providers_endpoint_returns_34_providers(self):
        status, data = self.request("/v1/providers")
        self.assertEqual(status, 200)
        self.assertEqual(data["total_providers"], 34)
        self.assertEqual(len(data["providers"]), 34)

    def test_post_v1_chat_completions_openai_compatible(self):
        payload = {
            "model": "meta-llama/llama-3.3-70b-instruct:free",
            "messages": [{"role": "user", "content": "Hello, generate a school bus tracker component"}],
        }
        status, data = self.request("/v1/chat/completions", method="POST", payload=payload)
        self.assertEqual(status, 200)
        self.assertEqual(data["object"], "chat.completion")
        self.assertIn("choices", data)
        self.assertEqual(len(data["choices"]), 1)
        self.assertIn("content", data["choices"][0]["message"])
        self.assertEqual(data["usage"]["cost_usd"], 0.0)

    def test_post_octopus_chat_endpoint(self):
        # 1. Ambiguous prompt triggers clarifying questions
        status, data = self.request("/octopus/chat", method="POST", payload={"prompt": "build an app"})
        self.assertEqual(status, 200)
        self.assertTrue(data["needs_clarification"])
        self.assertIn("questions", data)

        # 2. Detailed prompt dispatches mission
        status, data = self.request("/octopus/chat", method="POST", payload={"prompt": "Chess game arena with 8x8 playable board"})
        self.assertEqual(status, 200)
        self.assertTrue(data["understood"])
        self.assertIn("preview_url", data)

    def test_get_octopus_state_endpoint(self):
        status, data = self.request("/octopus/state")
        self.assertEqual(status, 200)
        self.assertIn("grand_head", data)
        self.assertIn("heads", data)
        self.assertEqual(len(data["heads"]), 6)

    def test_ai_keys_management_and_test_endpoints(self):
        # 1. Post keys
        payload = {
            "gemini": "AIzaSyTestKey12345678",
            "groq": "gsk_testGroqKey12345678",
            "active_provider": "gemini",
        }
        status, data = self.request("/ai/keys", method="POST", payload=payload)
        self.assertEqual(status, 200)
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["active_provider"], "gemini")

        # 2. Get keys status
        status, data = self.request("/ai/keys", method="GET")
        self.assertEqual(status, 200)
        self.assertTrue(data["gemini"]["configured"])
        self.assertTrue(data["groq"]["configured"])
        self.assertEqual(data["active_provider"], "gemini")

        # 3. Test ping provider — real verification now issues a real HTTP call.
        # The test key "AIzaSyTestKey12345678" is not a real Gemini credential,
        # so the real provider will reject it. We mock the HTTP layer to confirm
        # that an honest failure (not a fabricated success) is returned when the
        # provider rejects the key, and that a mocked success returns correctly.
        from unittest.mock import patch
        import urllib.error
        import json as _json

        # Sub-case A: provider correctly rejects a test/dummy key
        class _FakeAuthError(urllib.error.HTTPError):
            def __init__(self):
                super().__init__("http://mock", 403, "Forbidden", {}, None)
            def read(self):
                return b'{"error": {"code": 403, "status": "PERMISSION_DENIED"}}'

        with patch("software_factory.provider_verification.urllib.request.urlopen") as mu:
            mu.side_effect = _FakeAuthError()
            status, data = self.request("/ai/keys/test", method="POST", payload={"provider": "gemini"})
        self.assertEqual(status, 200)
        self.assertFalse(data["connected"])
        self.assertIn(data["status"], {"AUTHENTICATION_FAILED", "PROVIDER_MISMATCH"})

        # Sub-case B: mocked success — provider accepts the key
        gemini_mock_response = {"models": [{"name": "models/gemini-1.5-flash"}]}
        raw = _json.dumps(gemini_mock_response).encode("utf-8")
        from unittest.mock import MagicMock
        cm = MagicMock()
        cm.__enter__ = MagicMock(return_value=cm)
        cm.__exit__ = MagicMock(return_value=False)
        cm.status = 200
        cm.read = MagicMock(return_value=raw)
        with patch("software_factory.provider_verification.urllib.request.urlopen", return_value=cm):
            status, data = self.request("/ai/keys/test", method="POST", payload={"provider": "gemini"})
        self.assertEqual(status, 200)
        self.assertTrue(data["connected"])
        self.assertEqual(data["status"], "CONNECTED")
        self.assertGreater(data["latency_ms"], 0)


if __name__ == "__main__":
    unittest.main()

