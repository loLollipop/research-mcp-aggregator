"""Tests that research-mcp registers only local tools."""

import pytest

from research_mcp.server import ResearchMCPServer


@pytest.mark.asyncio
async def test_server_registers_local_tools_without_mcp_bridge():
    server = ResearchMCPServer()
    await server.initialize()
    try:
        tool_names = set(server._tools)
        assert "mcp_bridge_status" not in tool_names
        assert not any("__" in name for name in tool_names)
        assert "latex_check_config" in tool_names
        assert "docx_create" in tool_names
        assert "origin_check_config" in tool_names
        assert "origin_export_graph" in tool_names
        assert "simulation_workflow_template" in tool_names
    finally:
        await server.shutdown()
