import json
import tempfile
import unittest
from pathlib import Path
from software_factory.api_registry import ApiRegistry
from software_factory.catalogue_import import CatalogueImportError, import_records, load_records, preview

class CatalogueImportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.registry = ApiRegistry(self.root / "registry.sqlite3")
    def tearDown(self):
        self.tmp.cleanup()
    def row(self, **changes):
        row = {"name":"Example API","category":"developer-tools","source_url":"https://github.com/example/catalogue",
               "provider_url":"https://api.example.com","pricing_status":"UNKNOWN","licence_status":"UNKNOWN","notes":"curated"}
        row.update(changes)
        return row
    def test_preview_does_not_write(self):
        self.assertEqual(preview([self.row()], self.registry)["valid"], 1)
        self.assertEqual(self.registry.list(), [])
    def test_apply_stays_pending_and_unverified(self):
        import_records([self.row()], self.registry)
        item = self.registry.list()[0]
        self.assertEqual(item["approval_status"], "PENDING")
        self.assertEqual(item["verification_status"], "UNVERIFIED")
    def test_invalid_url_stops_before_write(self):
        with self.assertRaises(CatalogueImportError):
            import_records([self.row(source_url="http://bad.example")], self.registry)
        self.assertEqual(self.registry.list(), [])
    def test_duplicate_rows_stop_before_write(self):
        with self.assertRaises(CatalogueImportError):
            import_records([self.row(), self.row()], self.registry)
        self.assertEqual(self.registry.list(), [])
    def test_existing_duplicate_is_reported(self):
        self.registry.add("Example API", "developer-tools", "https://github.com/example/catalogue")
        self.assertEqual(len(preview([self.row()], self.registry)["duplicates"]), 1)
    def test_json_array_and_wrapped_payload(self):
        for payload in ([self.row()], {"apis":[self.row()]}):
            p = self.root / "in.json"; p.write_text(json.dumps(payload), encoding="utf-8")
            self.assertEqual(len(load_records(p)), 1)
    def test_csv(self):
        p = self.root / "in.csv"
        p.write_text("name,category,source_url\nExample API,developer-tools,https://github.com/example/catalogue\n", encoding="utf-8")
        self.assertEqual(len(load_records(p)), 1)
    def test_unknown_fields_rejected(self):
        p = self.root / "in.json"; p.write_text(json.dumps([self.row(extra="no")]), encoding="utf-8")
        with self.assertRaises(CatalogueImportError): load_records(p)
    def test_file_size_limit(self):
        p = self.root / "in.json"; p.write_text(json.dumps([self.row()] * 5001), encoding="utf-8")
        with self.assertRaises(CatalogueImportError): load_records(p)

if __name__ == "__main__":
    unittest.main()
