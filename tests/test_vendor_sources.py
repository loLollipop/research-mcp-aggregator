"""Tests for upstream MCP source audit workflow."""

import json
from pathlib import Path

import pytest

from scripts.audit_external_mcps import audit_source
from scripts.vendor_external_mcps import get_sources, load_manifest

ROOT = Path(__file__).resolve().parents[1]


def test_external_source_manifest_tracks_core_solver_mcps():
    manifest = load_manifest(ROOT / "external_mcp_sources.json")
    keys = {source["key"] for source in manifest["sources"]}
    assert manifest["strategy"] == "vendor-for-source-audit-and-porting"
    assert "external MCP servers" in manifest["runtime_policy"]
    assert {"pfc-mcp", "ansys-mcp-server", "comsol-multiphysics-mcp", "comsol-mcp"} <= keys


@pytest.mark.parametrize("key", ["pfc-mcp", "ansys-mcp-server", "comsol-multiphysics-mcp"])
def test_sources_have_audit_metadata(key):
    manifest = load_manifest(ROOT / "external_mcp_sources.json")
    source = get_sources(manifest, [key])[0]
    assert source["repo"].startswith("https://github.com/")
    assert source["target"].startswith("vendors/external/")
    assert source["expected_capabilities"]
    assert source["audit_status"] == "pending"


def test_get_sources_rejects_unknown_key():
    manifest = load_manifest(ROOT / "external_mcp_sources.json")
    with pytest.raises(ValueError, match="Unknown source keys"):
        get_sources(manifest, ["missing-mcp"])


def test_audit_source_reports_missing_vendor_tree(tmp_path):
    source = {
        "key": "demo-mcp",
        "repo": "https://github.com/example/demo.git",
        "target": "vendors/external/demo-mcp",
        "domain": "simulation/demo",
        "priority": 1,
    }
    result = audit_source(source, project_root=tmp_path)
    assert result["status"] == "missing"
    assert result["exists"] is False
    assert "vendor_external_mcps.py" in result["recommendation"]


def test_audit_source_detects_python_project_and_candidates(tmp_path):
    target = tmp_path / "vendors" / "external" / "demo-mcp"
    target.mkdir(parents=True)
    (target / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
    (target / "LICENSE").write_text("MIT", encoding="utf-8")
    (target / "server.py").write_text(
        "from mcp.server.fastmcp import FastMCP\n"
        "def solve_with_pfc():\n"
        "    return 'itasca pfc history export'\n",
        encoding="utf-8",
    )
    source = {
        "key": "demo-mcp",
        "repo": "https://github.com/example/demo.git",
        "target": "vendors/external/demo-mcp",
        "domain": "simulation/pfc",
        "priority": 1,
        "expected_capabilities": ["PFC history export"],
        "porting_notes": "demo",
    }

    result = audit_source(source, project_root=tmp_path)

    assert result["status"] == "audited"
    assert result["python_project"] is True
    assert result["license_files"] == ["LICENSE"]
    assert "server.py" in result["entry_candidates"]
    assert "server.py" in result["mcp_registration_candidates"]
    assert "server.py" in result["porting_candidates"]


def test_manifest_is_valid_json():
    json.loads((ROOT / "external_mcp_sources.json").read_text(encoding="utf-8"))
