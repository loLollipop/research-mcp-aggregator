"""Tests for the local capability catalog adapter."""

import pytest

from research_mcp.adapters.external_mcp_adapter import ExternalMCPAdapter


@pytest.mark.asyncio
async def test_external_mcp_list_filters_comsol_as_local_capability():
    adapter = ExternalMCPAdapter()
    result = await adapter.list_servers("comsol")
    assert result["mode"] == "self_contained_research_mcp"
    assert result["count"] >= 1
    assert any("comsol_run_batch" in server["internal_tools"] for server in result["capabilities"])


@pytest.mark.asyncio
async def test_external_mcp_config_snippet_points_to_research_mcp():
    adapter = ExternalMCPAdapter()
    result = await adapter.config_snippet("pfc-mcp")
    server = result["snippet"]["mcpServers"]["engineering-research-mcp"]
    assert result["mode"] == "single_mcp_config"
    assert "pfc_run_script" in result["internal_tools"]
    assert server["args"] == ["-m", "research_mcp.server"]


@pytest.mark.asyncio
async def test_external_mcp_list_includes_maturity_metadata():
    adapter = ExternalMCPAdapter()
    result = await adapter.list_servers("simulation")

    assert result["count"] >= 1
    assert all("maturity" in capability for capability in result["capabilities"])
    assert any(capability["maturity"] == "experimental" for capability in result["capabilities"])
    assert all("workflow_roles" in capability for capability in result["capabilities"])


@pytest.mark.asyncio
async def test_engineering_workflow_template_uses_internal_tools():
    adapter = ExternalMCPAdapter()
    result = await adapter.workflow_template("laser waterjet rock breaking", "pfc", "paper")
    assert result["topic"] == "laser waterjet rock breaking"
    assert len(result["steps"]) == 6
    assert any("pfc_run_script" in tool for tool in result["steps"][2]["tools"])
    assert all("MCP" not in tool for step in result["steps"] for tool in step["tools"])
