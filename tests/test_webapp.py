"""Integration tests for the same-origin connected control room."""
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, urlopen

from software_factory.api_registry import ApiRegistry
from software_factory.core import Store
from software_factory.specs import SpecStore, build_plan
from software_factory.webapp import WebHandler


class ConnectedWebTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        database = str(Path(self.tmp.name) / "factory.sqlite3")
        WebHandler.store = Store(database)
        WebHandler.specs = SpecStore(WebHandler.store)
        WebHandler.api_registry = ApiRegistry(database)
        WebHandler.build_plan = staticmethod(build_plan)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), WebHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
        self.tmp.cleanup()

    def request(self, path, method="GET", body=None):
        payload = None if body is None else json.dumps(body).encode("utf-8")
        request = Request(self.base + path, data=payload, method=method,
                          headers={"Content-Type": "application/json"} if payload else {})
        with urlopen(request, timeout=3) as response:
            return response.status, response.headers.get("Content-Type", ""), response.read()

    def test_root_serves_connected_control_room(self):
        status, content_type, body = self.request("/")
        self.assertEqual(status, 200)
        self.assertIn("text/html", content_type)
        self.assertIn(b"Save project to factory", body)
        self.assertIn(b"Server projects", body)

    def test_project_created_via_api_is_available_from_another_request(self):
        status, _, body = self.request("/health")
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(body)["ok"])

        status, _, body = self.request("/projects", "POST", {
            "name": "Cross-device project",
            "idea": "Persistent server-side record",
        })
        self.assertEqual(status, 201)
        created = json.loads(body)
        self.assertEqual(created["name"], "Cross-device project")

        status, _, body = self.request("/projects")
        self.assertEqual(status, 200)
        items = json.loads(body)["items"]
        self.assertEqual([item["id"] for item in items], [created["id"]])


if __name__ == "__main__":
    unittest.main()
