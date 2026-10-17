import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch
from pathlib import Path

from software_factory.api_registry import ApiRegistry, RegistryError, main


class ApiRegistryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "registry.sqlite3"
        self.registry = ApiRegistry(self.path)

    def tearDown(self):
        self.temp.cleanup()

    def candidate(self, **overrides):
        values = {"name": "Example Search API", "category": "developer-tools",
                  "source_url": "https://github.com/example/catalogue",
                  "provider_url": "https://api.example.com"}
        values.update(overrides)
        return self.registry.add(**values)

    def test_add_is_pending_and_persists_after_reopen(self):
        created = self.candidate()
        self.assertEqual(created["approval_status"], "PENDING")
        self.assertEqual(created["verification_status"], "UNVERIFIED")
        self.assertEqual(ApiRegistry(self.path).get(created["id"])["name"], "Example Search API")

    def test_rejects_non_https_and_embedded_credentials(self):
        with self.assertRaises(RegistryError):
            self.candidate(source_url="http://example.com/catalogue")
        with self.assertRaises(RegistryError):
            self.candidate(source_url="https://user:secret@example.com/catalogue")

    def test_duplicate_source_and_name_is_rejected(self):
        self.candidate()
        with self.assertRaises(RegistryError):
            self.candidate()

    def test_search_and_category_filter(self):
        self.candidate()
        self.candidate(name="Weather API", category="weather", source_url="https://example.com/weather")
        self.assertEqual(len(self.registry.list(query="search")), 1)
        self.assertEqual(len(self.registry.list(category="weather")), 1)

    def test_cannot_approve_unverified_or_unknown_licence_and_pricing(self):
        item = self.candidate()
        with self.assertRaises(RegistryError):
            self.registry.decide(item["id"], "APPROVED")
        self.registry.review(item["id"], verification_status="VERIFIED",
                             licence_status="UNKNOWN", pricing_status="FREE")
        with self.assertRaises(RegistryError):
            self.registry.decide(item["id"], "APPROVED")
        self.registry.review(item["id"], verification_status="VERIFIED",
                             licence_status="APPROVED", pricing_status="UNKNOWN")
        with self.assertRaises(RegistryError):
            self.registry.decide(item["id"], "APPROVED")

    def test_review_then_approve(self):
        item = self.candidate()
        reviewed = self.registry.review(item["id"], verification_status="VERIFIED",
                                        licence_status="APPROVED", pricing_status="FREEMIUM",
                                        notes="Provider documentation reviewed.")
        self.assertEqual(reviewed["approval_status"], "PENDING")
        approved = self.registry.decide(item["id"], "APPROVED", reason="Approved for adapter prototype")
        self.assertEqual(approved["approval_status"], "APPROVED")
        self.assertIn("Approved for adapter prototype", approved["notes"])

    def test_review_change_revokes_previous_approval(self):
        item = self.candidate()
        self.registry.review(item["id"], verification_status="VERIFIED",
                             licence_status="APPROVED", pricing_status="FREE")
        self.registry.decide(item["id"], "APPROVED")
        changed = self.registry.review(item["id"], verification_status="UNVERIFIED",
                                       licence_status="UNKNOWN", pricing_status="UNKNOWN")
        self.assertEqual(changed["approval_status"], "PENDING")

    def test_registry_mutations_write_audit_events(self):
        item = self.candidate()
        self.registry.review(item["id"], verification_status="VERIFIED",
                             licence_status="APPROVED", pricing_status="FREE", actor="reviewer")
        self.registry.decide(item["id"], "APPROVED", reason="Reviewed", actor="owner")
        events = self.registry.events(item["id"])
        self.assertEqual([event["kind"] for event in events], [
            "candidate.created", "candidate.reviewed", "candidate.decision",
        ])
        self.assertEqual([event["actor"] for event in events], ["system", "reviewer", "owner"])
        self.assertEqual(events[-1]["payload"]["approval_status"], "APPROVED")

    def test_cli_supports_review_decision_and_audit_history(self):
        output = io.StringIO()
        with patch("sys.argv", [
            "api_registry", "--database", str(self.path), "add",
            "--name", "CLI API", "--category", "developer-tools",
            "--source-url", "https://example.com/catalogue",
        ]), redirect_stdout(output):
            main()
        candidate_id = json.loads(output.getvalue())["id"]

        output = io.StringIO()
        with patch("sys.argv", [
            "api_registry", "--database", str(self.path), "review",
            "--id", str(candidate_id), "--verification", "VERIFIED",
            "--licence", "APPROVED", "--pricing", "FREE",
            "--notes", "Official provider terms checked", "--actor", "reviewer",
        ]), redirect_stdout(output):
            main()
        self.assertEqual(json.loads(output.getvalue())["approval_status"], "PENDING")

        output = io.StringIO()
        with patch("sys.argv", [
            "api_registry", "--database", str(self.path), "decide",
            "--id", str(candidate_id), "--status", "APPROVED",
            "--reason", "Suitable for evaluation", "--actor", "owner",
        ]), redirect_stdout(output):
            main()
        self.assertEqual(json.loads(output.getvalue())["approval_status"], "APPROVED")

        output = io.StringIO()
        with patch("sys.argv", [
            "api_registry", "--database", str(self.path), "events",
            "--candidate-id", str(candidate_id),
        ]), redirect_stdout(output):
            main()
        self.assertEqual([e["kind"] for e in json.loads(output.getvalue())], [
            "candidate.created", "candidate.reviewed", "candidate.decision",
        ])

    def test_invalid_status_is_rejected(self):
        item = self.candidate()
        with self.assertRaises(RegistryError):
            self.registry.review(item["id"], verification_status="MAYBE",
                                 licence_status="UNKNOWN", pricing_status="UNKNOWN")


if __name__ == "__main__":
    unittest.main()
