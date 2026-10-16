import tempfile
import unittest
from pathlib import Path
from software_factory.api_registry import ApiRegistry
from software_factory.provider_adapters import AdapterError, AdapterRegistry

class DemoAdapter:
    provider_key = "demo-provider"
    supported_operations = frozenset({"lookup"})
    def invoke(self, operation, payload, *, timeout_seconds):
        raise AssertionError("Registry must not invoke provider code")

class ProviderAdapterRegistryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.catalogue = ApiRegistry(Path(self.temp.name) / "registry.sqlite3")
        self.adapters = AdapterRegistry(self.catalogue)
        self.item = self.catalogue.add("Demo", "developer-tools", "https://example.com/catalogue", provider_url="https://api.example.com", pricing_status="FREE", licence_status="APPROVED")
    def tearDown(self):
        self.temp.cleanup()
    def approve(self):
        self.catalogue.review(self.item["id"], verification_status="VERIFIED", licence_status="APPROVED", pricing_status="FREE", notes="Reviewed official docs")
        self.catalogue.decide(self.item["id"], "APPROVED", reason="Owner approved")
    def test_unapproved_candidate_cannot_register(self):
        with self.assertRaisesRegex(AdapterError, "must be approved"):
            self.adapters.register(self.item["id"], DemoAdapter())
    def test_approved_candidate_resolves_allowlisted_operation_without_invoking(self):
        self.approve(); adapter = DemoAdapter(); self.adapters.register(self.item["id"], adapter)
        self.assertIs(self.adapters.resolve(self.item["id"], "lookup"), adapter)
        self.assertEqual(self.adapters.registered_candidates(), [self.item["id"]])
    def test_disallowed_operation_rejected(self):
        self.approve(); self.adapters.register(self.item["id"], DemoAdapter())
        with self.assertRaisesRegex(AdapterError, "not allowlisted"):
            self.adapters.resolve(self.item["id"], "delete")
    def test_review_change_blocks_existing_adapter(self):
        self.approve(); self.adapters.register(self.item["id"], DemoAdapter())
        self.catalogue.review(self.item["id"], verification_status="UNVERIFIED", licence_status="UNKNOWN", pricing_status="UNKNOWN")
        with self.assertRaisesRegex(AdapterError, "not currently approved"):
            self.adapters.resolve(self.item["id"], "lookup")
    def test_duplicate_registration_rejected(self):
        self.approve(); self.adapters.register(self.item["id"], DemoAdapter())
        with self.assertRaisesRegex(AdapterError, "already registered"):
            self.adapters.register(self.item["id"], DemoAdapter())
    def test_missing_candidate_or_adapter_rejected(self):
        with self.assertRaisesRegex(AdapterError, "does not exist"):
            self.adapters.resolve(999, "lookup")
        self.approve()
        with self.assertRaisesRegex(AdapterError, "No explicitly registered"):
            self.adapters.resolve(self.item["id"], "lookup")
    def test_empty_operation_allowlist_rejected(self):
        class BadAdapter:
            provider_key = "bad"
            supported_operations = frozenset()
            def invoke(self, operation, payload, *, timeout_seconds): return {}
        self.approve()
        with self.assertRaisesRegex(AdapterError, "non-empty"):
            self.adapters.register(self.item["id"], BadAdapter())

if __name__ == "__main__": unittest.main()
