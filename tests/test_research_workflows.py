"""Tests for workflow-level research planning tools."""

import pytest

from research_mcp.adapters.workflow_adapter import WorkflowAdapter
from research_mcp.server import ResearchMCPServer


@pytest.mark.asyncio
async def test_research_capability_list_filters_by_maturity_and_role():
    adapter = WorkflowAdapter()
    await adapter.initialize({})

    result = await adapter.capability_list(maturity="experimental", workflow_role="simulation")

    assert result["count"] >= 1
    assert all(capability["maturity"] == "experimental" for capability in result["capabilities"])
    assert any(capability["key"] == "comsol" for capability in result["capabilities"])


@pytest.mark.asyncio
async def test_literature_review_plan_uses_existing_literature_and_zotero_tools():
    adapter = WorkflowAdapter()
    await adapter.initialize({})

    result = await adapter.literature_review_plan(
        topic="laser waterjet rock breaking",
        time_range="2020-2026",
        target_venues=["Rock Mechanics and Rock Engineering"],
    )

    assert result["workflow"] == "literature_review"
    assert result["topic"] == "laser waterjet rock breaking"
    stage_tools = {tool for stage in result["stages"] for tool in stage["tools"]}
    assert "arxiv_search" in stage_tools
    assert "zotero_add_by_doi" in stage_tools
    assert "format_bibtex" in stage_tools


@pytest.mark.asyncio
async def test_simulation_study_plan_marks_live_solvers_as_external_requirements():
    adapter = WorkflowAdapter()
    await adapter.initialize({})

    result = await adapter.simulation_study_plan(
        research_question="How does water pressure change fracture propagation?",
        solver="pfc",
        parameters=["water_pressure"],
        observables=["crack_count"],
    )

    assert result["workflow"] == "simulation_study"
    assert result["solver"] == "pfc"
    assert any("local solver" in service for service in result["required_services"])
    assert any("pfc_parse_history" in stage["tools"] for stage in result["stages"])


@pytest.mark.asyncio
async def test_paper_asset_pack_uses_format_specific_submission_tools():
    adapter = WorkflowAdapter()
    await adapter.initialize({})

    result = await adapter.paper_asset_pack(
        title="Laser waterjet manuscript",
        claims=["Laser waterjet improves rock-breaking efficiency"],
        output_format="docx",
    )

    stage_tools = {stage["stage"]: stage["tools"] for stage in result["stages"]}
    assert "docx_read" in stage_tools["submission_readiness"]
    assert "latex_validate_project" not in stage_tools["submission_readiness"]
    assert "python-docx" in result["required_services"]
    assert "LaTeX toolchain for PDF builds" not in result["required_services"]


@pytest.mark.asyncio
async def test_server_registers_and_invokes_research_workflow_tool():
    server = ResearchMCPServer()
    await server.initialize({})
    try:
        assert "research_literature_review_plan" in server._tools
        spec, _ = server._tools["research_literature_review_plan"]
        result = await spec.handler(topic="AI-assisted engineering simulation")
    finally:
        await server.shutdown()

    assert result["workflow"] == "literature_review"
    assert result["topic"] == "AI-assisted engineering simulation"
