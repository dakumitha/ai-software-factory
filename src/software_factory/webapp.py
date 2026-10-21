"""Serve the responsive control room and JSON API from one local origin.

Remote binding remains disabled unless the operator explicitly opts in. This
module is a development convenience, not an authenticated production host.
"""
from __future__ import annotations

import os
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .api_registry import ApiRegistry
from .core import ApiHandler, Store
from .specs import SpecStore, build_plan


class WebHandler(ApiHandler):
    """Serve the connected control-room page; inherit all existing API routes."""

    def do_GET(self) -> None:
        from urllib.parse import urlparse

        path = urlparse(self.path).path
        if path in {"/", "/index.html"}:
            page = Path(__file__).resolve().parents[2] / "web" / "connected.html"
            try:
                payload = page.read_bytes()
            except OSError:
                return self._send(503, {"error": "Control-room page is unavailable."})
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(payload)
            return
        super().do_GET()


def serve_web(host: str = "127.0.0.1", port: int = 8080,
              database: str = "data/factory.sqlite3") -> None:
    """Run the same-origin UI/API locally; do not expose without production auth."""
    if host not in {"127.0.0.1", "localhost", "::1"} and os.environ.get("FACTORY_ALLOW_REMOTE") != "1":
        raise RuntimeError(
            "Remote binding is disabled by default. Do not expose this development "
            "server publicly; use authenticated TLS and a hardened deployment."
        )
    WebHandler.store = Store(database)
    WebHandler.specs = SpecStore(WebHandler.store)
    WebHandler.api_registry = ApiRegistry(database)
    WebHandler.build_plan = staticmethod(build_plan)
    WebHandler.load_persisted_keys()
    server = ThreadingHTTPServer((host, port), WebHandler)
    print(f"AI Software Factory connected control room: http://{host}:{port}")
    print(f"Database: {database}; remote worker: not connected; agent execution: disabled")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
