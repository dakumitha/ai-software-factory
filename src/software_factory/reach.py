"""Zero-Cost External Documentation and API Reach Engine for Coding Agents.

Inspired by Agent-Reach (https://github.com/Panniantong/Agent-Reach),
this module gives swarm agents zero-fee access to fetch, parse, and verify technical
documentation, third-party API contracts (Firebase, Razorpay, OpenStreetMap), and schema specs
without incurring search API bills or external SaaS subscription costs.
"""
from __future__ import annotations

import html
import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ReachResult:
    """Retrieved technical documentation or API schema contract."""
    source_url: str
    title: str
    content_text: str
    schema_definitions: dict[str, Any] = field(default_factory=dict)
    cached: bool = False
    status_code: int = 200


class AgentReachEngine:
    """Zero-cost knowledge and documentation retriever with offline cache."""

    # Pre-seeded verified offline contracts for primary tech stack
    OFFLINE_CONTRACTS = {
        "firebase_firestore": {
            "title": "Firebase Firestore Web SDK v9 Modular API Contract",
            "schema": {
                "methods": ["getFirestore", "collection", "doc", "getDoc", "setDoc", "addDoc", "query", "where", "onSnapshot"],
                "collections": ["students", "routes", "attendance_logs", "guardians", "schools", "payments"],
            },
            "summary": "Modular Firestore client configuration with typed collection references and real-time listeners.",
        },
        "razorpay_checkout": {
            "title": "Razorpay Standard Checkout & Webhook Verification API Contract",
            "schema": {
                "checkout_options": ["key", "amount", "currency", "order_id", "handler", "prefill", "theme"],
                "webhook_events": ["payment.captured", "payment.failed", "order.paid"],
                "verification_algorithm": "HMAC-SHA256 (order_id + '|' + payment_id, secret)",
            },
            "summary": "Client-side Razorpay modal invocation and server-side cryptographic signature verification.",
        },
        "transport_gps": {
            "title": "Vehicle Telemetry and Geolocation Contract",
            "schema": {
                "fields": ["bus_id", "route_id", "latitude", "longitude", "speed_kmh", "heading", "timestamp", "next_stop_id"],
                "update_interval_sec": 5,
            },
            "summary": "Real-time GPS vehicle coordinates stream for student transport tracking.",
        },
    }

    def __init__(self, cache_dir: str | Path | None = None, timeout_seconds: float = 10.0):
        self.cache_dir = Path(cache_dir) if cache_dir else None
        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.timeout = timeout_seconds

    def get_contract(self, domain_key: str) -> ReachResult | None:
        """Retrieve pre-seeded verified architecture contract for known platforms."""
        key = domain_key.lower().replace("-", "_")
        if key in self.OFFLINE_CONTRACTS:
            data = self.OFFLINE_CONTRACTS[key]
            return ReachResult(
                source_url=f"offline://contracts/{key}",
                title=data["title"],
                content_text=data["summary"],
                schema_definitions=data["schema"],
                cached=True,
                status_code=200,
            )
        return None

    def fetch_url_content(self, url: str) -> ReachResult:
        """Fetch external documentation or API spec at zero cost with sanitization."""
        # Check cache if directory is configured
        if self.cache_dir:
            cache_file = self.cache_dir / f"{abs(hash(url))}.json"
            if cache_file.exists():
                try:
                    cached_data = json.loads(cache_file.read_text(encoding="utf-8"))
                    return ReachResult(
                        source_url=url,
                        title=cached_data.get("title", url),
                        content_text=cached_data.get("content", ""),
                        schema_definitions=cached_data.get("schema", {}),
                        cached=True,
                        status_code=200,
                    )
                except Exception:
                    pass

        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "AI-Software-Factory-AgentReach/1.0 (Zero-Cost Research)",
                "Accept": "text/html,application/json,text/plain",
            },
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                status = resp.status
                raw = resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            return ReachResult(source_url=url, title="Fetch Error", content_text=f"HTTP {e.code}: {e.reason}", status_code=e.code)
        except Exception as e:
            return ReachResult(source_url=url, title="Network Error", content_text=str(e), status_code=500)

        # Parse text / title
        title_match = re.search(r"<title>(.*?)</title>", raw, re.IGNORECASE)
        title = title_match.group(1).strip() if title_match else url

        # Strip html tags for clean agent reading
        text = re.sub(r"<script.*?</script>", "", raw, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<style.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
        cleaned_text = " ".join(text.split())[:12000]

        result = ReachResult(source_url=url, title=title, content_text=cleaned_text, status_code=status)

        # Cache result
        if self.cache_dir:
            try:
                cache_file = self.cache_dir / f"{abs(hash(url))}.json"
                cache_file.write_text(json.dumps({"title": title, "content": cleaned_text}), encoding="utf-8")
            except Exception:
                pass

        return result

