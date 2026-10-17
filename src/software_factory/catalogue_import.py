"""Preview-first importer for operator-supplied local API catalogue JSON/CSV files."""
from __future__ import annotations
import argparse
import csv
import json
from pathlib import Path
from typing import Any
from .api_registry import ApiRegistry, RegistryError, LICENCE, PRICING, _url

REQUIRED = {"name", "category", "source_url"}
OPTIONAL = {"provider_url", "pricing_status", "licence_status", "notes"}

class CatalogueImportError(ValueError):
    """Catalogue input cannot be safely imported."""

def load_records(path: str | Path) -> list[dict[str, Any]]:
    file = Path(path)
    try:
        raw = file.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise CatalogueImportError(f"Cannot read input file: {exc}") from exc
    if file.suffix.lower() == ".csv":
        records = list(csv.DictReader(raw.splitlines()))
    elif file.suffix.lower() == ".json":
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise CatalogueImportError(f"Invalid JSON: {exc}") from exc
        records = payload.get("apis", payload.get("records")) if isinstance(payload, dict) else payload
    else:
        raise CatalogueImportError("Input must be a .json or .csv file.")
    if not isinstance(records, list):
        raise CatalogueImportError("JSON must be an array or contain an 'apis'/'records' array.")
    if len(records) > 5000:
        raise CatalogueImportError("Import is limited to 5000 records per file.")
    for i, row in enumerate(records, 1):
        if not isinstance(row, dict):
            raise CatalogueImportError(f"Record {i} must be an object/CSV row.")
        missing, unknown = REQUIRED - row.keys(), row.keys() - REQUIRED - OPTIONAL
        if missing:
            raise CatalogueImportError(f"Record {i} missing fields: {', '.join(sorted(missing))}.")
        if unknown:
            raise CatalogueImportError(f"Record {i} has unsupported fields: {', '.join(sorted(unknown))}.")
        if any(not isinstance(v, str) for v in row.values()):
            raise CatalogueImportError(f"Record {i} fields must all be text.")
    return records

def _validate(row: dict[str, Any]) -> None:
    name = row["name"].strip()
    category = row["category"].strip().lower()
    if not name or len(name) > 200:
        raise RegistryError("name is required and must be at most 200 characters.")
    if not category or len(category) > 80:
        raise RegistryError("category is required and must be at most 80 characters.")
    _url(row["source_url"], "source_url", required=True)
    _url(row.get("provider_url", ""), "provider_url")
    if row.get("pricing_status", "UNKNOWN").strip().upper() not in PRICING:
        raise RegistryError(f"pricing_status must be one of {sorted(PRICING)}.")
    if row.get("licence_status", "UNKNOWN").strip().upper() not in LICENCE:
        raise RegistryError(f"licence_status must be one of {sorted(LICENCE)}.")
    if len(row.get("notes", "")) > 4000:
        raise RegistryError("notes must be text no longer than 4000 characters.")

def preview(records: list[dict[str, Any]], registry: ApiRegistry) -> dict[str, Any]:
    seen = set()
    existing = {(x["name"].casefold(), x["source_url"]) for x in registry.list()}
    valid, duplicates, errors = [], [], []
    for i, row in enumerate(records, 1):
        name, source = row.get("name", "").strip(), row.get("source_url", "").strip()
        key = (name.casefold(), source)
        if key in seen or key in existing:
            duplicates.append({"row": i, "name": name, "source_url": source})
            continue
        seen.add(key)
        try:
            _validate(row)
        except (RegistryError, AttributeError) as exc:
            errors.append({"row": i, "error": str(exc)})
            continue
        valid.append({"row": i, "name": name, "category": row["category"].strip().lower(), "source_url": source})
    return {"total": len(records), "valid": len(valid), "duplicates": duplicates, "errors": errors, "candidates": valid}

def import_records(records: list[dict[str, Any]], registry: ApiRegistry, actor: str = "catalogue-import") -> dict[str, Any]:
    report = preview(records, registry)
    if report["errors"] or report["duplicates"]:
        raise CatalogueImportError("Import stopped before writing: fix all validation errors and duplicates.")
    added = []
    for row in records:
        item = registry.add(row["name"], row["category"], row["source_url"],
            provider_url=row.get("provider_url", ""), pricing_status=row.get("pricing_status", "UNKNOWN"),
            licence_status=row.get("licence_status", "UNKNOWN"), notes=row.get("notes", ""), actor=actor)
        added.append({"id": item["id"], "name": item["name"], "approval_status": item["approval_status"]})
    return {"imported": len(added), "records": added,
            "note": "Records remain PENDING and UNVERIFIED until operator review."}

def main() -> None:
    parser = argparse.ArgumentParser(description="Preview/import a local curated API catalogue file")
    parser.add_argument("file")
    parser.add_argument("--database", default="data/api-registry.sqlite3")
    parser.add_argument("--apply", action="store_true", help="Persist; default is preview-only")
    parser.add_argument("--actor", default="catalogue-import")
    args = parser.parse_args()
    try:
        records = load_records(args.file)
        registry = ApiRegistry(args.database)
        result = import_records(records, registry, args.actor) if args.apply else preview(records, registry)
        print(json.dumps({"mode": "apply" if args.apply else "preview", **result}, indent=2, ensure_ascii=False))
    except (CatalogueImportError, RegistryError) as exc:
        parser.error(str(exc))

if __name__ == "__main__":
    main()
