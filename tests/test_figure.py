"""Tests for the figure adapter."""

import pytest

from research_mcp.adapters.figure_adapter import FigureAdapter


@pytest.mark.asyncio
async def test_plot_xy(tmp_path):
    adapter = FigureAdapter()
    await adapter.initialize({})
    output = tmp_path / "plot.svg"
    result = await adapter.plot_xy([1, 2, 3], [2, 4, 6], str(output), xlabel="x", ylabel="y")
    assert output.exists()
    assert result["points"] == 3
    assert result["kind"] == "line"
