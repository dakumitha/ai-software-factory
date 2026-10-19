"""Tests for Universal Autonomous Application Synthesizer & App Factory Endpoints."""
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
    UniversalAppPackage,
    UniversalAppSynthesizer,
)


class UniversalSynthesizerTests(unittest.TestCase):
    def setUp(self):
        self.synthesizer = UniversalAppSynthesizer()

    def test_deconstruct_gaming_domain(self):
        bp = self.synthesizer.deconstruct_prompt("Build an online multiplayer chess game with ranking ladder")
        self.assertIn("Gaming", bp.category)
        self.assertIn("Player", bp.stakeholders)
        entity_names = [e["name"] for e in bp.entities]
        self.assertIn("GameState", entity_names)
        self.assertIn("PlayerProfile", entity_names)

    def test_deconstruct_finance_domain(self):
        bp = self.synthesizer.deconstruct_prompt("Crypto portfolio tracker with live price alerts and instant swap")
        self.assertIn("Financial Technology", bp.category)
        self.assertIn("Investor", bp.stakeholders)
        entity_names = [e["name"] for e in bp.entities]
        self.assertIn("Asset", entity_names)
        self.assertIn("Transaction", entity_names)

    def test_deconstruct_fitness_domain(self):
        bp = self.synthesizer.deconstruct_prompt("Gym workout log with rep timer and body weight metrics")
        self.assertIn("Health, Fitness", bp.category)
        self.assertIn("Athlete", bp.stakeholders)
        entity_names = [e["name"] for e in bp.entities]
        self.assertIn("WorkoutSession", entity_names)

    def test_deconstruct_culinary_domain(self):
        bp = self.synthesizer.deconstruct_prompt("Pantry leftover cooking recipe generator and grocery list")
        self.assertIn("Culinary", bp.category)
        self.assertIn("Home Chef", bp.stakeholders)
        entity_names = [e["name"] for e in bp.entities]
        self.assertIn("Recipe", entity_names)

    def test_deconstruct_social_domain(self):
        bp = self.synthesizer.deconstruct_prompt("Community chat forum with real-time direct messaging channels")
        self.assertIn("Social Collaboration", bp.category)
        self.assertIn("Member", bp.stakeholders)
        entity_names = [e["name"] for e in bp.entities]
        self.assertIn("Channel", entity_names)

    def test_deconstruct_general_productivity_fallback(self):
        bp = self.synthesizer.deconstruct_prompt("Enterprise warehouse fleet tracking and audit logs")
        self.assertIn("Productivity Platform", bp.category)
        self.assertIn("Operator", bp.stakeholders)
        entity_names = [e["name"] for e in bp.entities]
        self.assertIn("WorkItem", entity_names)

    def test_synthesize_application_end_to_end(self):
        pkg = self.synthesizer.synthesize_application(
            prompt="Build a multiplayer arcade puzzle game with leaderboard",
            user_title="Arcade Puzzle Rush",
        )
        self.assertEqual(pkg.blueprint.title, "Arcade Puzzle Rush")
        self.assertTrue(pkg.syntax_verified)
        self.assertEqual(pkg.spend_usd, 0.0)
        self.assertGreater(pkg.total_files, 4)
        self.assertIn("pnpm-workspace.yaml", pkg.files)
        self.assertIn("turbo.json", pkg.files)
        self.assertIn("packages/shared/types/models.ts", pkg.files)
        self.assertIn("Arcade Puzzle Rush", pkg.preview_html)

    def test_package_export_to_directory(self):
        pkg = self.synthesizer.synthesize_application("Multiplayer chess platform")
        with tempfile.TemporaryDirectory() as tmp_dir:
            dest = pkg.export(tmp_dir)
            self.assertTrue(Path(dest).exists())
            self.assertTrue((Path(dest) / "pnpm-workspace.yaml").exists())
            self.assertTrue((Path(dest) / "turbo.json").exists())
            self.assertTrue((Path(dest) / "preview.html").exists())
            self.assertIn("<!doctype html>", (Path(dest) / "preview.html").read_text(encoding="utf-8"))


class UniversalAppApiTests(unittest.TestCase):
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

    def request(self, path: str, payload: dict | None = None, is_html: bool = False):
        url = f"http://127.0.0.1:{self.port}{path}"
        data = None
        headers = {}
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = Request(url, data=data, headers=headers)
        try:
            with urlopen(req) as resp:
                status = resp.status
                raw = resp.read()
                if is_html:
                    return status, raw.decode("utf-8")
                return status, json.loads(raw.decode("utf-8"))
        except HTTPError as exc:
            raw = exc.read().decode("utf-8")
            try:
                data = json.loads(raw)
            except Exception:
                data = {"raw": raw}
            return exc.code, data

    def test_synthesize_app_api_and_preview(self):
        status, app = self.request("/apps/synthesize", {
            "prompt": "Crypto portfolio tracker with instant swap and price alert triggers",
            "title": "CryptoPulse Pro",
        })
        self.assertEqual(status, 201)
        self.assertEqual(app["title"], "CryptoPulse Pro")
        self.assertEqual(app["spend_usd"], 0.0)
        self.assertTrue(app["syntax_verified"])
        self.assertIn("preview_url", app)

        # GET /apps
        status, apps_list = self.request("/apps")
        self.assertEqual(status, 200)
        self.assertGreaterEqual(apps_list["count"], 1)

        # GET /apps/<id>
        status, app_meta = self.request(f"/apps/{app['app_id']}")
        self.assertEqual(status, 200)
        self.assertEqual(app_meta["title"], "CryptoPulse Pro")

        # GET /apps/<id>/preview
        status, preview_html = self.request(f"/apps/{app['app_id']}/preview", is_html=True)
        self.assertEqual(status, 200)
        self.assertIn("CryptoPulse Pro", preview_html)
        self.assertIn("<!doctype html>", preview_html)

        # POST /apps/<id>/export
        with tempfile.TemporaryDirectory() as export_dest:
            status, exp_result = self.request(f"/apps/{app['app_id']}/export", {
                "target_dir": export_dest,
            })
            self.assertEqual(status, 200)
            self.assertTrue((Path(export_dest) / "preview.html").exists())
            self.assertTrue((Path(export_dest) / "blueprint.json").exists())


if __name__ == "__main__":
    unittest.main()
