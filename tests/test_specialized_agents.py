"""Unit tests for the 8 Specialized Domain Agents and Swarm Engine."""
from __future__ import annotations

import json
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from software_factory.core import ApiHandler, Store
from software_factory.api_registry import ApiRegistry
from software_factory.specs import SpecStore, build_plan
from software_factory.universal_synthesizer import (
    AppArchitectureBlueprint,
    UniversalAppSynthesizer,
)
from software_factory.specialized_agents import (
    ArchitectAgent,
    ClawAgent,
    CoderAgent,
    DesignAgent,
    QaAgent,
    ReaAgent,
    ReconAgent,
    SecurityAgent,
    SpecializedAgentSwarm,
)


class SpecializedAgentsTests(unittest.TestCase):
    def setUp(self):
        self.synthesizer = UniversalAppSynthesizer()
        self.bp = self.synthesizer.deconstruct_prompt(
            "Online multiplayer chess game with move validation and leaderboards",
            user_title="Grandmaster Arena",
        )
        self.pkg = self.synthesizer.synthesize_application(
            "Online multiplayer chess game with move validation and leaderboards",
            user_title="Grandmaster Arena",
        )

    def test_recon_agent_discovers_libraries(self):
        agent = ReconAgent()
        res = agent.run("Multiplayer chess game", "Gaming")
        self.assertEqual(res.role_name, "recon_scout")
        self.assertEqual(res.status, "COMPLETED")
        repos = res.artifacts["recommended_repositories"]
        self.assertGreaterEqual(len(repos), 2)
        repo_names = [r["repo"] for r in repos]
        self.assertTrue(any("chess" in r for r in repo_names))

    def test_rea_agent_extracts_clean_room_requirements(self):
        agent = ReaAgent()
        res = agent.run(self.bp)
        self.assertEqual(res.role_name, "reverse_engineering_specialist")
        self.assertEqual(res.status, "VERIFIED")
        self.assertTrue(res.artifacts["clean_room_verified"])
        self.assertEqual(res.artifacts["proprietary_pollution"], "0.00%")

    def test_architect_agent_designs_monorepo_models(self):
        agent = ArchitectAgent()
        res = agent.run(self.bp)
        self.assertEqual(res.role_name, "system_architect")
        self.assertEqual(res.status, "VERIFIED")
        self.assertIn("PlayerProfile", res.artifacts["models"])
        self.assertEqual(res.artifacts["contract_file"], "packages/shared/types/models.ts")

    def test_design_agent_synthesizes_tokens(self):
        agent = DesignAgent()
        res = agent.run(self.bp)
        self.assertEqual(res.role_name, "ui_ux_specialist")
        self.assertEqual(res.status, "VERIFIED")
        self.assertIn("color.primary", res.artifacts["tokens"])

    def test_coder_agent_synthesizes_components(self):
        agent = CoderAgent()
        res = agent.run(self.pkg)
        self.assertEqual(res.role_name, "autonomous_coder")
        self.assertEqual(res.status, "VERIFIED")
        self.assertIn("apps/web/src/App.tsx", res.artifacts["files_manifest"])

    def test_security_agent_scans_clean_files(self):
        agent = SecurityAgent()
        res = agent.run(self.pkg.files)
        self.assertEqual(res.role_name, "strix_security_auditor")
        self.assertEqual(res.status, "VERIFIED")
        self.assertEqual(res.artifacts["risk_level"], "CLEAN")

    def test_qa_agent_validates_syntax_and_hash(self):
        agent = QaAgent()
        res = agent.run(self.pkg)
        self.assertEqual(res.role_name, "qa_sentinel")
        self.assertEqual(res.status, "VERIFIED")
        self.assertTrue(res.artifacts["syntax_clean"])
        self.assertTrue(len(res.artifacts["integrity_hash"]) > 0)

    def test_claw_agent_binds_webhooks(self):
        agent = ClawAgent()
        res = agent.run(self.bp)
        self.assertEqual(res.role_name, "claw_dispatcher")
        self.assertEqual(res.status, "COMPLETED")
        self.assertIn("WhatsApp", res.artifacts["supported_channels"])

    def test_specialized_swarm_end_to_end_orchestration(self):
        swarm = SpecializedAgentSwarm(synthesizer=self.synthesizer)
        report = swarm.execute_swarm("Fitness gym workout set logger and calorie tracker", user_title="IronFit")
        self.assertEqual(report.app_title, "IronFit")
        self.assertEqual(report.status, "VERIFIED_AND_DELIVERED")
        self.assertEqual(len(report.specialists), 8)
        self.assertEqual(report.total_spend_usd, 0.0)
        roles = [s.role_name for s in report.specialists]
        self.assertIn("recon_scout", roles)
        self.assertIn("reverse_engineering_specialist", roles)
        self.assertIn("system_architect", roles)
        self.assertIn("ui_ux_specialist", roles)
        self.assertIn("autonomous_coder", roles)
        self.assertIn("strix_security_auditor", roles)
        self.assertIn("qa_sentinel", roles)
        self.assertIn("claw_dispatcher", roles)


class SpecializedAgentsApiTests(unittest.TestCase):
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
        self.thread.join(timeout=2)
        import gc
        gc.collect()
        self.tmp.cleanup()

    def request(self, path: str, payload: dict | None = None):
        url = f"http://127.0.0.1:{self.port}{path}"
        data = None
        headers = {}
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = Request(url, data=data, headers=headers)
        try:
            with urlopen(req) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except HTTPError as exc:
            raw = exc.read().decode("utf-8")
            try:
                data = json.loads(raw)
            except Exception:
                data = {"raw": raw}
            return exc.code, data

    def test_get_specialists_roster(self):
        status, data = self.request("/swarm/specialists")
        self.assertEqual(status, 200)
        self.assertIn("specialists", data)
        self.assertEqual(len(data["specialists"]), 8)

    def test_run_specialists_swarm_api(self):
        status, report = self.request("/swarm/specialists/run", {
            "prompt": "Multiplayer arcade puzzle rush",
            "title": "Puzzle Rush API",
        })
        self.assertEqual(status, 200)
        self.assertEqual(report["app_title"], "Puzzle Rush API")
        self.assertEqual(len(report["specialists"]), 8)

    def test_apps_synthesize_includes_specialists_trace(self):
        status, app = self.request("/apps/synthesize", {
            "prompt": "Smart recipe generator and pantry leftover organizer",
            "title": "KitchenAI",
        })
        self.assertEqual(status, 201)
        self.assertEqual(app["title"], "KitchenAI")
        self.assertIn("specialists", app)
        self.assertEqual(len(app["specialists"]), 8)


if __name__ == "__main__":
    unittest.main()

