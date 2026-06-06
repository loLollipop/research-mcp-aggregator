"""Audit vendored upstream MCP repositories for migration planning."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

try:
    from scripts.vendor_external_mcps import MANIFEST, ROOT, get_sources, load_manifest
except ModuleNotFoundError:
    from vendor_external_mcps import MANIFEST, ROOT, get_sources, load_manifest

PYTHON_MARKERS = ("pyproject.toml", "setup.py", "requirements.txt")
NODE_MARKERS = ("package.json", "pnpm-lock.yaml", "yarn.lock", "package-lock.json")
LICENSE_NAMES = ("LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING")
ENTRY_GLOBS = ("**/server.py", "**/main.py", "**/index.ts", "**/index.js", "**/app.py")
MCP_PATTERNS = ("FastMCP", "mcp.server", "@modelcontextprotocol", "list_tools", "call_tool", "Tool")
PORTING_KEYWORDS = (
    "comsol",
    "mph",
    "livelink",
    "pyfluent",
    "ansys",
    "fluent",
    "itasca",
    "pfc",
    "fish",
    "history",
    "solve",
    "export",
)


def relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def find_existing(root: Path, names: tuple[str, ...]) -> list[str]:
    return [name for name in names if (root / name).exists()]


def find_entries(root: Path) -> list[str]:
    paths: list[Path] = []
    for pattern in ENTRY_GLOBS:
        paths.extend(root.glob(pattern))
    return sorted({relative(path, root) for path in paths if ".venv" not in path.parts})[:30]


def file_contains(path: Path, patterns: tuple[str, ...]) -> bool:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False
    lowered = text.lower()
    return any(pattern.lower() in lowered for pattern in patterns)


def find_matching_files(root: Path, patterns: tuple[str, ...], limit: int = 40) -> list[str]:
    matches: list[str] = []
    for path in root.rglob("*"):
        if len(matches) >= limit:
            break
        if not path.is_file() or ".git" in path.parts or ".venv" in path.parts:
            continue
        if path.suffix.lower() not in {".py", ".ts", ".js", ".json", ".md", ".toml"}:
            continue
        if file_contains(path, patterns):
            matches.append(relative(path, root))
    return matches


def recommend_porting(
    python_markers: list[str], node_markers: list[str], licenses: list[str]
) -> str:
    if not licenses:
        return "Check upstream license before copying code; prefer API ideas over direct migration."
    if python_markers:
        return (
            "Prefer porting Python backend modules into research_mcp "
            "simulation backends with attribution."
        )
    if node_markers:
        return (
            "Port behavior/design selectively; direct TypeScript runtime reuse "
            "is not ideal for this Python MCP."
        )
    return "Inspect manually; project type is unclear from top-level markers."


def audit_source(source: dict[str, Any], project_root: Path = ROOT) -> dict[str, Any]:
    target = project_root / source["target"]
    result: dict[str, Any] = {
        "key": source["key"],
        "repo": source["repo"],
        "target": source["target"],
        "domain": source["domain"],
        "priority": source.get("priority"),
        "exists": target.exists(),
    }
    if not target.exists():
        result["status"] = "missing"
        result["recommendation"] = (
            "Run scripts/vendor_external_mcps.py for this key before auditing."
        )
        return result

    python_markers = find_existing(target, PYTHON_MARKERS)
    node_markers = find_existing(target, NODE_MARKERS)
    licenses = find_existing(target, LICENSE_NAMES)
    result.update(
        {
            "status": "audited",
            "python_project": bool(python_markers),
            "node_project": bool(node_markers),
            "python_markers": python_markers,
            "node_markers": node_markers,
            "license_files": licenses,
            "entry_candidates": find_entries(target),
            "mcp_registration_candidates": find_matching_files(target, MCP_PATTERNS),
            "porting_candidates": find_matching_files(target, PORTING_KEYWORDS),
            "expected_capabilities": source.get("expected_capabilities", []),
            "porting_notes": source.get("porting_notes", ""),
            "porting_recommendation": recommend_porting(python_markers, node_markers, licenses),
        }
    )
    return result


def audit_manifest(
    manifest_path: Path = MANIFEST,
    project_root: Path = ROOT,
    keys: list[str] | None = None,
) -> list[dict[str, Any]]:
    manifest = load_manifest(manifest_path)
    return [audit_source(source, project_root) for source in get_sources(manifest, keys)]


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit vendored upstream MCP source trees")
    parser.add_argument("keys", nargs="*", help="Optional source keys to audit")
    parser.add_argument("--output", default="vendors/audit_report.json", help="JSON output path")
    args = parser.parse_args()

    report = audit_manifest(keys=args.keys)
    output = (ROOT / args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote audit report: {output}")
    for item in report:
        print(f"- {item['key']}: {item['status']}")


if __name__ == "__main__":
    main()
