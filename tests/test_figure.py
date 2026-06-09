"""Tests for the figure adapter."""

import pytest

from research_mcp.adapters.figure_adapter import MAX_PLOT_POINTS, FigureAdapter


@pytest.mark.asyncio
async def test_plot_xy(tmp_path):
    adapter = FigureAdapter()
    await adapter.initialize({})
    output = tmp_path / "plot.svg"
    result = await adapter.plot_xy([1, 2, 3], [2, 4, 6], str(output), xlabel="x", ylabel="y")
    assert output.exists()
    assert result["points"] == 3
    assert result["kind"] == "line"


@pytest.mark.asyncio
async def test_plot_xy_rejects_too_many_points(tmp_path):
    adapter = FigureAdapter()
    await adapter.initialize({})
    too_many = [0.0] * (MAX_PLOT_POINTS + 1)

    with pytest.raises(ValueError, match="supports at most"):
        await adapter.plot_xy(too_many, too_many, str(tmp_path / "plot.svg"))
