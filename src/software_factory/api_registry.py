"""Persistent, review-gated catalogue of candidate external APIs.

This module records discovery metadata only. It never fetches, invokes, or installs
third-party services. External listings are untrusted until reviewed by an operator.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

PRICING = {"UNKNOWN", "FREE", "FREEMIUM", "PAID"}
LICENCE = {"UNKNOWN", "APPROVED", "RESTRICTED", "NOT_APPLICABLE"}
VERIFICATION = {"UNVERIFIED", "VERIFIED", "REJECTED"}
APPROVAL = {"PENDING", "APPROVED", "REJECTED"}


class RegistryError(ValueError):
    """A registry record is invalid or violates review policy."""


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _url(value: str, field: str, required: bool = False) -> str:
    if not isinstance(value, str):
        raise RegistryError(f"{field} must be a URL string.")
    value = value.strip()
    if not value and not required:
        return ""
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        raise RegistryError(f"{field} must be an HTTPS URL without embedded credentials.")
    return value


class ApiRegistry:
    """SQLite-backed directory of external API candidates."""

    def __init__(self, path: str | Path = "data/api-registry.sqlite3"):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS api_candidates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    category TEXT NOT NULL,
                    source_url TEXT NOT NULL,
                    provider_url TEXT NOT NULL DEFAULT '',
                    pricing_status TEXT NOT NULL,
                    licence_status TEXT NOT NULL,
                    verification_status TEXT NOT NULL,
                    approval_status TEXT NOT NULL,
                    notes TEXT NOT NULL DEFAULT '',
                    last_verified_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(name, source_url)
                )
            """)
            db.execute("CREATE INDEX IF NOT EXISTS idx_api_candidates_category ON api_candidates(category)")
            db.execute("CREATE INDEX IF NOT EXISTS idx_api_candidates_review ON api_candidates(approval_status, verification_status)")

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    @staticmethod
    def _record(row: sqlite3.Row) -> dict:
        return dict(row)

    def add(self, name: str, category: str, source_url: str, *,
            provider_url: str = "", pricing_status: str = "UNKNOWN",
            licence_status: str = "UNKNOWN", notes: str = "") -> dict:
        name = name.strip() if isinstance(name, str) else ""
        category = category.strip().lower() if isinstance(category, str) else ""
        if not name or len(name) > 200:
            raise RegistryError("name is required and must be at most 200 characters.")
        if not category or len(category) > 80:
            raise RegistryError("category is required and must be at most 80 characters.")
        source_url = _url(source_url, "source_url", required=True)
        provider_url = _url(provider_url, "provider_url")
        pricing_status = pricing_status.upper()
        licence_status = licence_status.upper()
        if pricing_status not in PRICING:
            raise RegistryError(f"pricing_status must be one of {sorted(PRICING)}.")
        if licence_status not in LICENCE:
            raise RegistryError(f"licence_status must be one of {sorted(LICENCE)}.")
        if not isinstance(notes, str) or len(notes) > 4000:
            raise RegistryError("notes must be text no longer than 4000 characters.")
        now = now_utc()
        try:
            with self._connect() as db:
                cur = db.execute("""
                    INSERT INTO api_candidates
                    (name, category, source_url, provider_url, pricing_status, licence_status,
                     verification_status, approval_status, notes, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, 'UNVERIFIED', 'PENDING', ?, ?, ?)
                """, (name, category, source_url, provider_url, pricing_status, licence_status,
                      notes.strip(), now, now))
                row = db.execute("SELECT * FROM api_candidates WHERE id=?", (cur.lastrowid,)).fetchone()
        except sqlite3.IntegrityError as exc:
            raise RegistryError("This API candidate is already registered with the same source URL.") from exc
        return self._record(row)

    def get(self, candidate_id: int) -> dict | None:
        with self._connect() as db:
            row = db.execute("SELECT * FROM api_candidates WHERE id=?", (candidate_id,)).fetchone()
        return self._record(row) if row else None

    def list(self, *, query: str = "", category: str = "", approval_status: str = "") -> list[dict]:
        sql = "SELECT * FROM api_candidates WHERE 1=1"
        args: list[str] = []
        if query.strip():
            term = "%" + query.strip().lower() + "%"
            sql += " AND (lower(name) LIKE ? OR lower(category) LIKE ? OR lower(notes) LIKE ?)"
            args.extend([term, term, term])
        if category.strip():
            sql += " AND category=?"
            args.append(category.strip().lower())
        if approval_status.strip():
            status = approval_status.strip().upper()
            if status not in APPROVAL:
                raise RegistryError(f"approval_status must be one of {sorted(APPROVAL)}.")
            sql += " AND approval_status=?"
            args.append(status)
        sql += " ORDER BY updated_at DESC, id DESC"
        with self._connect() as db:
            return [self._record(row) for row in db.execute(sql, args).fetchall()]

    def review(self, candidate_id: int, *, verification_status: str,
               licence_status: str, pricing_status: str, notes: str = "") -> dict:
        verification_status = verification_status.upper()
        licence_status = licence_status.upper()
        pricing_status = pricing_status.upper()
        if verification_status not in VERIFICATION:
            raise RegistryError(f"verification_status must be one of {sorted(VERIFICATION)}.")
        if licence_status not in LICENCE or pricing_status not in PRICING:
            raise RegistryError("Invalid licence_status or pricing_status.")
        if not isinstance(notes, str) or len(notes) > 4000:
            raise RegistryError("notes must be text no longer than 4000 characters.")
        now = now_utc()
        verified_at = now if verification_status == "VERIFIED" else None
        with self._connect() as db:
            row = db.execute("SELECT * FROM api_candidates WHERE id=?", (candidate_id,)).fetchone()
            if not row:
                raise RegistryError("API candidate does not exist.")
            db.execute("""
                UPDATE api_candidates SET verification_status=?, licence_status=?, pricing_status=?,
                    approval_status='PENDING', notes=?, last_verified_at=?, updated_at=? WHERE id=?
            """, (verification_status, licence_status, pricing_status,
                  notes.strip() or row["notes"], verified_at, now, candidate_id))
            updated = db.execute("SELECT * FROM api_candidates WHERE id=?", (candidate_id,)).fetchone()
        return self._record(updated)

    def decide(self, candidate_id: int, approval_status: str, *, reason: str = "") -> dict:
        approval_status = approval_status.upper()
        if approval_status not in APPROVAL:
            raise RegistryError(f"approval_status must be one of {sorted(APPROVAL)}.")
        if not isinstance(reason, str) or len(reason) > 2000:
            raise RegistryError("reason must be text no longer than 2000 characters.")
        with self._connect() as db:
            row = db.execute("SELECT * FROM api_candidates WHERE id=?", (candidate_id,)).fetchone()
            if not row:
                raise RegistryError("API candidate does not exist.")
            if approval_status == "APPROVED":
                if row["verification_status"] != "VERIFIED":
                    raise RegistryError("Approval requires verification_status=VERIFIED.")
                if row["licence_status"] not in {"APPROVED", "NOT_APPLICABLE"}:
                    raise RegistryError("Approval requires an approved or not-applicable licence status.")
                if row["pricing_status"] == "UNKNOWN":
                    raise RegistryError("Approval requires a known pricing status.")
            notes = row["notes"]
            if reason.strip():
                notes = (notes + "\nDecision: " + reason.strip()).strip()
            db.execute("UPDATE api_candidates SET approval_status=?, notes=?, updated_at=? WHERE id=?",
                       (approval_status, notes[:4000], now_utc(), candidate_id))
            updated = db.execute("SELECT * FROM api_candidates WHERE id=?", (candidate_id,)).fetchone()
        return self._record(updated)


def main() -> None:
    parser = argparse.ArgumentParser(description="Review-gated API discovery registry")
    parser.add_argument("--database", default="data/api-registry.sqlite3")
    sub = parser.add_subparsers(dest="command", required=True)
    add = sub.add_parser("add", help="Record a candidate without invoking it")
    add.add_argument("--name", required=True)
    add.add_argument("--category", required=True)
    add.add_argument("--source-url", required=True)
    add.add_argument("--provider-url", default="")
    add.add_argument("--pricing", choices=sorted(PRICING), default="UNKNOWN")
    add.add_argument("--licence", choices=sorted(LICENCE), default="UNKNOWN")
    add.add_argument("--notes", default="")
    listing = sub.add_parser("list", help="List/search candidates")
    listing.add_argument("--query", default="")
    listing.add_argument("--category", default="")
    listing.add_argument("--status", default="")
    args = parser.parse_args()
    registry = ApiRegistry(args.database)
    try:
        if args.command == "add":
            result = registry.add(args.name, args.category, args.source_url,
                                  provider_url=args.provider_url, pricing_status=args.pricing,
                                  licence_status=args.licence, notes=args.notes)
        else:
            result = registry.list(query=args.query, category=args.category,
                                   approval_status=args.status)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except RegistryError as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
