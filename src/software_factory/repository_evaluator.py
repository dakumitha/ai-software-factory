"""Static, non-executing assessment of a local source repository.

The evaluator reads a bounded set of metadata files. It never clones repositories,
installs dependencies, runs build scripts, imports project code, or executes plugins.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

MAX_FILE_BYTES = 1_000_000
MANIFESTS = {
    "package.json": "Node.js / JavaScript / TypeScript",
    "pyproject.toml": "Python",
    "Cargo.toml": "Rust",
    "go.mod": "Go",
    "requirements.txt": "Python (requirements file)",
}
LICENSE_NAMES = ("LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING")
LOCKFILES = ("pnpm-lock.yaml", "package-lock.json", "yarn.lock", "bun.lock", "bun.lockb",
             "uv.lock", "poetry.lock", "Cargo.lock")


def _read(root: Path, relative: str) -> str | None:
    path = root / relative
    try:
        if not path.is_file() or path.stat().st_size > MAX_FILE_BYTES:
            return None
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def evaluate_repository(directory: str | Path) -> dict:
    """Return a reproducible metadata-only report for a local repository."""
    root = Path(directory).expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"Repository directory does not exist or is not a directory: {root}")

    readme = _read(root, "README.md")
    present_manifests = [name for name in MANIFESTS if _read(root, name) is not None]
    license_file = next((name for name in LICENSE_NAMES if _read(root, name) is not None), None)
    lockfiles = [name for name in LOCKFILES if _read(root, name) is not None]
    workflow_dir = root / ".github" / "workflows"
    try:
        workflows = sorted(p.name for p in workflow_dir.iterdir()
                           if p.is_file() and p.suffix.lower() in {".yml", ".yaml"}) if workflow_dir.is_dir() else []
    except OSError:
        workflows = []
    tests = any((root / name).is_dir() for name in ("tests", "test", "__tests__", "spec"))
    package_json = _read(root, "package.json")
    scripts = {}
    package_parse_error = False
    if package_json is not None:
        try:
            parsed = json.loads(package_json)
            scripts = parsed.get("scripts", {}) if isinstance(parsed, dict) else {}
            if not isinstance(scripts, dict):
                scripts = {}
                package_parse_error = True
        except json.JSONDecodeError:
            package_parse_error = True

    indicators = []
    score = 0

    def add(name: str, passed: bool, points: int, detail: str) -> None:
        nonlocal score
        indicators.append({"check": name, "passed": bool(passed), "points": points if passed else 0, "detail": detail})
        if passed:
            score += points

    add("README", bool(readme and readme.strip()), 10, "README.md present and readable" if readme else "README.md missing or unreadable")
    add("Project manifest", bool(present_manifests), 15,
        ", ".join(present_manifests) if present_manifests else "No recognised project manifest found")
    add("Licence file", bool(license_file), 15,
        f"Found {license_file}; licence identity and compatibility still require review" if license_file else "No recognised licence file found")
    add("CI workflow", bool(workflows), 15,
        ", ".join(workflows) if workflows else "No GitHub Actions workflow files found")
    add("Test directory", tests, 15, "Recognised test directory found" if tests else "No conventional test directory found")
    add("Dependency lockfile", bool(lockfiles), 10,
        ", ".join(lockfiles) if lockfiles else "No recognised dependency lockfile found")
    security_policy = _read(root, "SECURITY.md") is not None
    add("Security policy", security_policy, 10,
        "SECURITY.md found" if security_policy else "SECURITY.md not found")
    add("Package scripts parse", package_json is None or not package_parse_error, 10,
        "package.json scripts parsed" if package_json is not None and not package_parse_error else
        ("package.json is invalid or scripts field is malformed" if package_parse_error else "Not applicable"))

    warnings = [
        "Static metadata review only. No dependency installation, build, tests, network fetch, or code execution was performed.",
        "A score is a triage aid, not a security certification, quality guarantee, or proof that the project builds.",
        "Review the exact revision, transitive dependency licences, maintenance activity, release provenance, and security advisories before adoption.",
    ]
    risky_scripts = sorted(k for k in scripts if k.lower() in {"preinstall", "install", "postinstall", "prepare"})
    if risky_scripts:
        warnings.append("package.json contains lifecycle scripts (" + ", ".join(risky_scripts) +
                        "); inspect their commands before any dependency installation.")
    if package_parse_error:
        warnings.append("package.json could not be parsed reliably; inspect it manually.")
    if not license_file:
        warnings.append("Do not assume a repository is reusable merely because it is public.")
    return {
        "schema_version": 1,
        "repository_path": str(root),
        "assessment_mode": "static_metadata_only",
        "score": min(100, score),
        "rating": "strong_metadata_signals" if score >= 75 else ("mixed_metadata_signals" if score >= 45 else "insufficient_metadata_signals"),
        "detected_stacks": [MANIFESTS[name] for name in present_manifests],
        "files": {
            "manifests": present_manifests,
            "licence_file": license_file,
            "lockfiles": lockfiles,
            "ci_workflows": workflows,
            "readme_present": bool(readme and readme.strip()),
            "test_directory_present": tests,
            "security_policy_present": security_policy,
        },
        "checks": indicators,
        "warnings": warnings,
        "adoption_status": "REVIEW_REQUIRED",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Statically evaluate a local repository without executing it")
    parser.add_argument("directory", help="Path to an already available local source repository")
    parser.add_argument("--output", help="Optional path for a JSON report; stdout is used by default")
    args = parser.parse_args()
    try:
        report = evaluate_repository(args.directory)
    except ValueError as exc:
        parser.error(str(exc))
    rendered = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        output = Path(args.output).expanduser()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered + "\n", encoding="utf-8")
        print(f"Report written to {output}")
        print(f"Score: {report['score']}/100; adoption status: {report['adoption_status']}")
    else:
        print(rendered)


if __name__ == "__main__":
    main()
