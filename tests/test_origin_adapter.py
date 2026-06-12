import importlib

import pytest

from research_mcp.adapters.origin_adapter import OriginAdapter


@pytest.mark.asyncio
async def test_origin_check_config_is_safe_without_connecting():
    adapter = OriginAdapter()

    result = await adapter.check_config()

    assert result["status"] == "ok"
    assert result["data"]["connected"] is False
    assert "originpro_available" in result["data"]
    assert "detected_installations" in result["data"]


@pytest.mark.asyncio
async def test_origin_get_info_gracefully_reports_missing_originpro(monkeypatch):
    adapter = OriginAdapter()

    def fail_import(name: str):
        if name == "originpro":
            raise ImportError("originpro not installed")
        return importlib.import_module(name)

    monkeypatch.setattr("research_mcp.adapters.origin_adapter.importlib.import_module", fail_import)

    result = await adapter.get_info()

    assert result["status"] == "error"
    assert result["error_type"] == "origin_unavailable"
    assert "research-mcp[origin]" in result["hint"]


@pytest.mark.asyncio
async def test_origin_execute_labtalk_blocks_file_and_project_commands():
    adapter = OriginAdapter()

    for command in ["save project.opju", "open test.opju", "expGraph type:=png", "doc -s"]:
        result = await adapter.execute_labtalk(command)
        assert result["status"] == "error"
        assert result["error_type"] == "blocked_unsafe_labtalk"


def test_origin_tool_names_are_prefixed():
    adapter = OriginAdapter()
    tool_names = {tool.name for tool in adapter.metadata().tools}

    assert "origin_check_config" in tool_names
    assert "origin_export_graph" in tool_names
    assert all(name.startswith("origin_") for name in tool_names)
