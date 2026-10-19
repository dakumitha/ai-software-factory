"""Tests for FigCraft design document builder, MCP protocol bridge, and React code generator."""
import json
import tempfile
import unittest
from pathlib import Path

from software_factory.figcraft import (
    FigCraftCodeGenerator,
    FigCraftDocument,
    FigCraftMcpBridge,
    FigCraftNode,
    FigCraftTemplateBuilder,
)
from software_factory.templates import generate_archetype_files


class FigCraftTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.tmp.name)

    def tearDown(self):
        import gc
        gc.collect()
        try:
            self.tmp.cleanup()
        except Exception:
            pass

    def test_figcraft_document_serialization(self):
        doc = FigCraftDocument(title="Test UI Design")
        frame = FigCraftNode(
            id="f1",
            name="Login Screen",
            node_type="FRAME",
            width=375,
            height=812,
            background_color="#000000",
        )
        doc.add_frame(frame)

        json_str = doc.to_json()
        data = json.loads(json_str)

        self.assertEqual(data["title"], "Test UI Design")
        self.assertGreaterEqual(len(data["tokens"]), 6)
        self.assertEqual(len(data["canvas"]["frames"]), 1)
        self.assertEqual(data["canvas"]["frames"][0]["id"], "f1")

    def test_figcraft_template_builder_school_transport(self):
        doc = FigCraftTemplateBuilder.build_school_transport_document("VidyaVahan School Transport")
        self.assertEqual(len(doc.frames), 3)

        frame_ids = {f.id for f in doc.frames}
        self.assertIn("frame-parent-mobile", frame_ids)
        self.assertIn("frame-driver-mobile", frame_ids)
        self.assertIn("frame-school-admin", frame_ids)

        parent_frame = next(f for f in doc.frames if f.id == "frame-parent-mobile")
        self.assertEqual(parent_frame.width, 390)
        self.assertEqual(parent_frame.height, 844)
        self.assertGreaterEqual(len(parent_frame.children), 3)

    def test_figcraft_code_generator_produces_valid_react(self):
        frame = FigCraftNode(
            id="frame-parent-tracking",
            name="Parent Bus Tracking Screen",
            node_type="FRAME",
            width=390,
            height=844,
            background_color="#0F172A",
            border_radius=24,
        )
        react_code = FigCraftCodeGenerator.frame_to_react(frame)
        self.assertIn("export function ParentBusTrackingScreenComponent()", react_code)
        self.assertIn("maxWidth: '390px'", react_code)
        self.assertIn("borderRadius: '24px'", react_code)

    def test_figcraft_mcp_bridge_tool_definitions(self):
        bridge = FigCraftMcpBridge(control_port=7979)
        tools = bridge.get_mcp_tools()
        self.assertEqual(len(tools), 2)
        tool_names = {t["name"] for t in tools}
        self.assertIn("figcraft_create_frame", tool_names)
        self.assertIn("figcraft_export_code", tool_names)

    def test_templates_scaffold_includes_figcraft_document(self):
        files = generate_archetype_files("school_transport", "VidyaVahan Test")
        self.assertIn("design/school_transport.figcraft.json", files)

        doc_data = json.loads(files["design/school_transport.figcraft.json"])
        self.assertEqual(doc_data["title"], "VidyaVahan Test")
        self.assertEqual(len(doc_data["canvas"]["frames"]), 3)


if __name__ == "__main__":
    unittest.main()

