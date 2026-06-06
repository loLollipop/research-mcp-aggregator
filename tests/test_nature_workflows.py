"""Tests for Nature-style manuscript workflow planning tools."""

import pytest

from research_mcp.adapters.nature_adapter import NatureManuscriptAdapter
from research_mcp.server import ResearchMCPServer


@pytest.mark.asyncio
async def test_nature_manuscript_plan_links_claims_figures_and_submission_checks():
    adapter = NatureManuscriptAdapter()
    await adapter.initialize({})

    result = await adapter.manuscript_plan(
        title="Laser waterjet fracture control",
        central_claim="Coupled laser-waterjet loading improves controllable rock fracture",
        target_journal="Nature Communications",
        claims=["Hybrid loading lowers fracture threshold"],
        figures=["mechanism schematic", "fracture propagation comparison"],
    )

    assert result["workflow"] == "nature_manuscript_plan"
    assert result["target_journal"] == "Nature Communications"
    assert result["claims"] == ["Hybrid loading lowers fracture threshold"]
    assert result["figures"] == ["mechanism schematic", "fracture propagation comparison"]
    stage_tools = {tool for stage in result["stages"] for tool in stage["tools"]}
    assert "research_literature_review_plan" in stage_tools
    assert "nature_figure_package_plan" in stage_tools
    assert "nature_submission_readiness_checklist" in stage_tools
    assert any("display item" in item for item in result["quality_bar"])


@pytest.mark.asyncio
async def test_nature_figure_package_plan_preserves_source_data_traceability():
    adapter = NatureManuscriptAdapter()
    await adapter.initialize({})

    result = await adapter.figure_package_plan(
        storyline="From mechanism to validation",
        claims=["PFC simulations reproduce observed fracture branching"],
        data_sources=["outputs/pfc_history.csv", "figures/source_data.xlsx"],
        preferred_format="pdf",
    )

    assert result["workflow"] == "nature_figure_package_plan"
    assert result["preferred_format"] == "pdf"
    assert "outputs/pfc_history.csv" in result["data_sources"]
    stage_names = [stage["stage"] for stage in result["stages"]]
    assert "source_data_traceability" in stage_names
    assert any("source data" in item for item in result["output_expectations"])


@pytest.mark.asyncio
async def test_nature_submission_checklist_is_format_and_modality_aware():
    adapter = NatureManuscriptAdapter()
    await adapter.initialize({})

    result = await adapter.submission_readiness_checklist(
        title="Laser waterjet fracture control",
        has_human_or_animal_data=True,
        has_code_outputs=True,
        has_simulation_outputs=True,
        output_format="both",
    )

    assert result["workflow"] == "nature_submission_readiness_checklist"
    validation_stage = next(
        stage for stage in result["stages"] if stage["stage"] == "manuscript_validation"
    )
    assert "latex_validate_project" in validation_stage["tools"]
    assert "docx_read" in validation_stage["tools"]
    assert any("ethics approvals" in check for check in result["checks"])
    assert any("solver versions" in check for check in result["checks"])


@pytest.mark.asyncio
async def test_nature_submission_checklist_rejects_unsupported_format():
    adapter = NatureManuscriptAdapter()
    await adapter.initialize({})

    with pytest.raises(ValueError, match="Unsupported output_format"):
        await adapter.submission_readiness_checklist(
            title="Laser waterjet fracture control",
            output_format="markdown",
        )


@pytest.mark.asyncio
async def test_server_registers_and_invokes_nature_workflow_tool():
    server = ResearchMCPServer()
    await server.initialize({})
    try:
        assert "nature_manuscript_plan" in server._tools
        spec, _ = server._tools["nature_manuscript_plan"]
        result = await spec.handler(
            title="AI-assisted engineering simulation",
            central_claim="Research MCPs can make simulation studies more reproducible",
        )
    finally:
        await server.shutdown()

    assert result["workflow"] == "nature_manuscript_plan"
    assert result["title"] == "AI-assisted engineering simulation"
