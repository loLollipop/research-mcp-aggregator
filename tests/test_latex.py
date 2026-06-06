"""Tests for the local LaTeX adapter."""

import pytest

from research_mcp.adapters.latex_adapter import LatexAdapter


@pytest.mark.asyncio
async def test_latex_check_config_defaults():
    adapter = LatexAdapter()
    await adapter.initialize({})
    status = await adapter.check_config()
    assert status["latex_cmd"] == "latexmk"
    assert status["timeout_seconds"] == 300


@pytest.mark.asyncio
async def test_latex_create_and_validate_minimal_project(tmp_path):
    adapter = LatexAdapter()
    await adapter.initialize({})
    created = await adapter.create_minimal_project(
        str(tmp_path / "paper"), "Test Paper", "A. Author"
    )
    result = await adapter.validate_project(created["main_tex"])
    assert result["valid"] is True
    assert result["has_documentclass"] is True


@pytest.mark.asyncio
async def test_latex_validate_resolves_common_implicit_extensions(tmp_path):
    adapter = LatexAdapter()
    await adapter.initialize({})
    project = tmp_path / "paper"
    project.mkdir()
    (project / "figure.png").write_text("image", encoding="utf-8")
    (project / "refs.bib").write_text("", encoding="utf-8")
    main_tex = project / "main.tex"
    main_tex.write_text(
        "\\documentclass{article}\n"
        "\\usepackage{graphicx}\n"
        "\\begin{document}\n"
        "\\includegraphics{figure}\n"
        "\\bibliography{refs}\n"
        "\\end{document}\n",
        encoding="utf-8",
    )

    result = await adapter.validate_project(str(main_tex))
    assert result["valid"] is True
    assert result["missing_assets"] == []
    assert result["referenced_assets"] == ["figure", "refs"]
