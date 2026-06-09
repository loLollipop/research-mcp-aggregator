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
    assert server["command"] == "research-mcp"
    assert "PYTHONPATH" not in server["env"]


@pytest.mark.asyncio
async def test_external_mcp_list_includes_maturity_metadata():
    adapter = ExternalMCPAdapter()
    result = await adapter.list_servers("simulation")

    assert result["count"] >= 1
    assert all("maturity" in capability for capability in result["capabilities"])
    assert any(capability["maturity"] == "experimental" for capability in result["capabilities"])
    assert all("workflow_roles" in capability for capability in result["capabilities"])


@pytest.mark.asyncio
async def test_external_mcp_list_includes_nature_workflow_capability():
    adapter = ExternalMCPAdapter()
    result = await adapter.list_servers("nature")

    assert result["count"] == 1
    capability = result["capabilities"][0]
    assert capability["key"] == "nature-manuscript"
    assert "nature_manuscript_plan" in capability["internal_tools"]
    assert "submission_readiness" in capability["workflow_roles"]


@pytest.mark.asyncio
async def test_external_mcp_list_includes_pdf_mineru_capability():
    adapter = ExternalMCPAdapter()
    result = await adapter.list_servers("pdf")

    assert result["count"] == 1
    capability = result["capabilities"][0]
    assert capability["key"] == "pdf-mineru"
    assert "pdf_extract_mineru" in capability["internal_tools"]
    assert "paper-pdf-reader" in capability["replaces"]
    assert "paper_reading" in capability["workflow_roles"]


@pytest.mark.asyncio
async def test_engineering_workflow_template_uses_internal_tools():
    adapter = ExternalMCPAdapter()
    result = await adapter.workflow_template("laser waterjet rock breaking", "pfc", "paper")
    assert result["topic"] == "laser waterjet rock breaking"
    assert len(result["steps"]) == 6
    assert "pdf_extract_mineru" in result["steps"][0]["tools"]
    assert any("pfc_run_script" in tool for tool in result["steps"][2]["tools"])
    assert all("MCP" not in tool for step in result["steps"] for tool in step["tools"])
