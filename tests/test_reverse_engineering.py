"""Tests for reverse engineering analysis bridge and specification generator."""
import tempfile
import unittest
from pathlib import Path

from software_factory.core import Store, ValidationError
from software_factory.reverse_engineering import (
    convert_rea_report_to_specification,
    parse_rea_analysis_report,
)
from software_factory.specs import SpecStore


class ReverseEngineeringTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "re_test.sqlite3"
        self.store = Store(self.db_path)
        self.project = self.store.create_project("Reverse Engineering Project", "Test REA bridge")
        self.spec_store = SpecStore(self.store)

    def tearDown(self):
        self.tmp.cleanup()

    def test_parse_rea_analysis_report_validations(self):
        with self.assertRaises(ValidationError):
            parse_rea_analysis_report("{invalid-json")

        with self.assertRaises(ValidationError):
            parse_rea_analysis_report(12345)

        raw = {
            "target_name": "Lovable Design Canvas",
            "components": [{"name": "ChatPromptInput"}, {"name": "PreviewCanvas"}],
            "unknowns": ["Does canvas use canvas2d or WebGL?"],
        }
        parsed = parse_rea_analysis_report(raw)
        self.assertEqual(parsed["target_name"], "Lovable Design Canvas")
        self.assertEqual(len(parsed["components"]), 2)
        self.assertEqual(len(parsed["unknowns"]), 1)

    def test_convert_rea_report_to_specification(self):
        rea_report = {
            "target_name": "Figma-Lovable Hybrid Studio",
            "components": [
                {
                    "name": "ComponentHierarchyTree",
                    "description": "Interactive tree view showing nested DOM/Figma elements",
                    "acceptance_criteria": ["Renders node hierarchy", "Supports node selection"],
                },
                {
                    "name": "LiveCodeEditor",
                    "description": "Code panel with syntax highlighting and auto-save",
                },
            ],
            "api_contracts": [
                {
                    "endpoint": "/api/generate-component",
                    "method": "POST",
                    "description": "Generate React/Tailwind component code from prompt",
                }
            ],
            "inferred_logic": [
                "Canvas uses CSS transform matrix for pan and zoom operations.",
                "Components communicate via a central reactive state store.",
            ],
            "limitations": [
                "Cannot decompile server-side LLM orchestrator weights.",
                "WebSocket protocol payload is encrypted end-to-end.",
            ],
            "unknowns": [
                "How are real-time multi-user cursor conflicts resolved?",
            ],
        }

        spec = convert_rea_report_to_specification(
            rea_report,
            title="Design-to-Code Platform",
            goal="Provide a verifiable clean-room design-to-code workspace.",
        )

        self.assertEqual(spec["title"], "Design-to-Code Platform")
        self.assertEqual(spec["goal"], "Provide a verifiable clean-room design-to-code workspace.")
        self.assertEqual(len(spec["requirements"]), 3)  # 2 components + 1 API
        self.assertEqual(len(spec["open_questions"]), 1)
        self.assertIn("cursor conflicts", spec["open_questions"][0])
        self.assertTrue(any("CSS transform" in a for a in spec["assumptions"]))
        self.assertTrue(any("LLM orchestrator" in c for c in spec["constraints"]))

        # Verify it saves cleanly into SpecStore
        saved = self.spec_store.save(self.project["id"], spec)
        self.assertEqual(saved["version"], 1)

        # Gated: cannot approve while open questions remain
        with self.assertRaises(ValidationError) as ctx:
            self.spec_store.approve(saved["id"])
        self.assertIn("open questions", str(ctx.exception))

        # Once open questions are resolved, approval succeeds
        spec["open_questions"] = []
        saved_v2 = self.spec_store.save(self.project["id"], spec)
        approved = self.spec_store.approve(saved_v2["id"])
        self.assertEqual(approved["status"], "APPROVED")


if __name__ == "__main__":
    unittest.main()

