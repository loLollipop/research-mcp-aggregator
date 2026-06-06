"""Vendor upstream MCP repositories for source audit and porting.

These repositories are cloned only for inspection and selected code migration.
They are not run as external MCP servers at research-mcp runtime.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "external_mcp_sources.json"


def load_manifest(path: Path = MANIFEST) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def get_sources(manifest: dict[str, Any], keys: list[str] | None = None) -> list[dict[str, Any]]:
    sources = manifest["sources"]
    if not keys:
        return sources
    wanted = set(keys)
    selected = [source for source in sources if source["key"] in wanted]
    missing = wanted - {source["key"] for source in selected}
    if missing:
        raise ValueError(f"Unknown source keys: {', '.join(sorted(missing))}")
    return selected


def run(cmd: list[str], cwd: Path | None = None) -> None:
    print("$", " ".join(cmd))
    subprocess.run(cmd, cwd=cwd, check=True)


def list_sources(sources: list[dict[str, Any]]) -> None:
    for source in sorted(sources, key=lambda item: item.get("priority", 999)):
        capabilities = "; ".join(source.get("expected_capabilities", []))
        print(f"{source['key']} [{source['domain']}] -> {source['target']}")
        print(f"  repo: {source['repo']}")
        print(f"  expected: {capabilities}")


def vendor_source(source: dict[str, Any], update: bool = False) -> None:
    target = ROOT / source["target"]
    repo = source["repo"]
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if update:
            run(["git", "pull", "--ff-only"], cwd=target)
        else:
            print(f"skip existing: {target}")
        return
    run(["git", "clone", "--depth", "1", repo, str(target)])


def main() -> None:
    parser = argparse.ArgumentParser(description="Vendor upstream MCP repos for source audit")
    parser.add_argument("keys", nargs="*", help="Source keys to vendor; default: all")
    parser.add_argument("--list", action="store_true", help="List sources without cloning")
    parser.add_argument("--update", action="store_true", help="Update already-vendored repos")
    args = parser.parse_args()

    manifest = load_manifest()
    print(manifest["runtime_policy"])
    sources = get_sources(manifest, args.keys)
    if args.list:
        list_sources(sources)
        return
    for source in sources:
        vendor_source(source, update=args.update)


if __name__ == "__main__":
    main()
