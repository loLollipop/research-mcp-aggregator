"""Tests for local PFC documentation tools ported from pfc-mcp."""

import pytest

from research_mcp.adapters.pfc_docs_adapter import PFCDocsAdapter
from research_mcp.server import ResearchMCPServer


@pytest.mark.asyncio
async def test_pfc_docs_status_available_after_vendor():
    adapter = PFCDocsAdapter()
    await adapter.initialize({})
    status = await adapter.status()
    assert status["available"] is True
    assert status["runtime_bridge_required"] is False
    assert status["source"] == "vendors/external/pfc-mcp"


@pytest.mark.asyncio
async def test_pfc_browse_command_categories_and_command_doc():
    adapter = PFCDocsAdapter()
    await adapter.initialize({})

    categories = await adapter.browse_commands()
    assert categories["count"] >= 1
    assert any(category["name"] == "ball" for category in categories["categories"])

    doc = await adapter.browse_commands("ball create")
    assert doc["action"] == "browse_command"
    assert doc["category"] == "ball"
    assert doc["command"] == "create"
    assert "syntax" in doc["doc"]


@pytest.mark.asyncio
async def test_pfc_query_command_uses_vendored_docs():
    adapter = PFCDocsAdapter()
    await adapter.initialize({})
    result = await adapter.query_command("ball create", limit=5)
    assert result["count"] >= 1
    assert any(match["category"] == "ball" for match in result["matches"])


@pytest.mark.asyncio
async def test_server_registers_pfc_docs_without_external_bridge():
    server = ResearchMCPServer()
    await server.initialize()
    try:
        tool_names = set(server._tools)
        assert "pfc_docs_status" in tool_names
        assert "pfc_browse_commands" in tool_names
        assert "pfc_query_command" in tool_names
        assert "pfc_browse_python_api" in tool_names
        assert "pfc_query_python_api" in tool_names
        assert "mcp_bridge_status" not in tool_names
        assert not any("__" in name for name in tool_names)
    finally:
        await server.shutdown()


@pytest.mark.asyncio
async def test_pfc_browse_python_api_root_module_and_function():
    adapter = PFCDocsAdapter()
    await adapter.initialize({})

    root = await adapter.browse_python_api()
    assert root["action"] == "browse_root"
    assert root["module_count"] >= 1
    assert any(module["path"] == "itasca.ball" for module in root["modules"])

    module = await adapter.browse_python_api("itasca.ball")
    assert module["action"] == "browse_module"
    assert module["module"]["module"] == "itasca.ball"

    func = await adapter.browse_python_api("itasca.ball.create")
    assert func["action"] == "browse_api"
    assert "create" in func["doc"].get("signature", "")


@pytest.mark.asyncio
async def test_pfc_query_python_api_uses_vendored_docs():
    adapter = PFCDocsAdapter()
    await adapter.initialize({})
    result = await adapter.query_python_api("ball create", limit=5)
    assert result["count"] >= 1
    assert any("ball" in match["api_path"] for match in result["matches"])
