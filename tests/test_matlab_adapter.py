"""Tests for the local MATLAB command-line adapter."""

from __future__ import annotations

import pytest

from research_mcp.adapters.matlab_adapter import MatlabAdapter
from research_mcp.external_catalog import get_capability
from research_mcp.server import ResearchMCPServer


@pytest.mark.asyncio
async def test_matlab_adapter_check_config_without_matlab_install():
    adapter = MatlabAdapter()

    await adapter.initialize({"matlab_cmd": "matlab", "timeout_seconds": 123})

    result = await adapter.check_config()
    assert result["matlab_cmd"] == "matlab"
    assert result["timeout_seconds"] == 123
    assert result["scope_notice"]["requires_user_review"] is True
    assert "matlab/matlab-mcp-core-server" in result["upstream_references"]


@pytest.mark.asyncio
async def test_matlab_create_script_writes_m_file(tmp_path):
    adapter = MatlabAdapter()
    await adapter.initialize({"matlab_cmd": "matlab"})
    script_path = tmp_path / "demo_script.m"

    result = await adapter.create_script(str(script_path), "x = 1;\ndisp(x);\n")

    assert result["status"] == "ok"
    assert script_path.read_text(encoding="utf-8") == "x = 1;\ndisp(x);\n"


@pytest.mark.asyncio
async def test_matlab_run_file_dry_run_builds_batch_command(tmp_path):
    adapter = MatlabAdapter()
    await adapter.initialize({"matlab_cmd": "matlab", "timeout_seconds": 99})
    script_path = tmp_path / "run_me.m"
    script_path.write_text("disp('hello')\n", encoding="utf-8")

    result = await adapter.run_file(str(script_path), dry_run=True)

    assert result["status"] == "dry_run"
    assert result["tool"] == "matlab_run_file"
    assert result["command"][0:2] == ["matlab", "-batch"]
    assert "run('" in result["command"][2]
    assert result["timeout_seconds"] == 99
    assert result["input_files"]["file_path"] == str(script_path.resolve())


@pytest.mark.asyncio
async def test_matlab_evaluate_code_dry_run_uses_working_dir(tmp_path):
    adapter = MatlabAdapter()
    await adapter.initialize({"matlab_cmd": "matlab"})

    result = await adapter.evaluate_code("disp(1)", working_dir=str(tmp_path), dry_run=True)

    assert result["status"] == "dry_run"
    assert result["cwd"] == str(tmp_path.resolve())
    assert result["command"] == ["matlab", "-batch", "disp(1)"]


@pytest.mark.asyncio
async def test_matlab_detect_toolboxes_dry_run_builds_struct_array_command(tmp_path):
    adapter = MatlabAdapter()
    await adapter.initialize({"matlab_cmd": "matlab"})

    result = await adapter.detect_toolboxes(working_dir=str(tmp_path), dry_run=True)

    assert result["status"] == "dry_run"
    assert result["tool"] == "matlab_detect_toolboxes"
    assert result["command"][0:2] == ["matlab", "-batch"]
    assert "Name = {v.Name}'" in result["command"][2]
    assert "struct2table(v(:," not in result["command"][2]


@pytest.mark.asyncio
async def test_matlab_parse_table_summarizes_numeric_columns(tmp_path):
    adapter = MatlabAdapter()
    table_path = tmp_path / "results.csv"
    table_path.write_text("time,value,label\n0,1.5,a\n1,2.5,b\n", encoding="utf-8")

    result = await adapter.parse_table(str(table_path), preview_rows=1)

    assert result["status"] == "ok"
    assert result["delimiter"] == ","
    assert result["row_count"] == 2
    assert result["columns"] == ["time", "value", "label"]
    assert result["preview_rows"] == [{"time": "0", "value": "1.5", "label": "a"}]
    assert result["numeric_summary"]["value"]["count"] == 2
    assert result["numeric_summary"]["value"]["min"] == 1.5
    assert result["numeric_summary"]["value"]["max"] == 2.5
    assert result["numeric_summary"]["value"]["mean"] == 2.0
    assert "label" not in result["numeric_summary"]


@pytest.mark.asyncio
async def test_matlab_parse_table_detects_tsv(tmp_path):
    adapter = MatlabAdapter()
    table_path = tmp_path / "results.tsv"
    table_path.write_text("x\ty\n1\t2\n", encoding="utf-8")

    result = await adapter.parse_table(str(table_path))

    assert result["delimiter"] == "\t"
    assert result["columns"] == ["x", "y"]


@pytest.mark.asyncio
async def test_matlab_parse_table_rejects_unknown_delimiter(tmp_path):
    adapter = MatlabAdapter()
    table_path = tmp_path / "results.csv"
    table_path.write_text("x,y\n1,2\n", encoding="utf-8")

    with pytest.raises(ValueError, match="delimiter must be one of"):
        await adapter.parse_table(str(table_path), delimiter="pipe")


@pytest.mark.asyncio
async def test_matlab_create_plot_export_script_writes_script(tmp_path):
    adapter = MatlabAdapter()
    table_path = tmp_path / "results.csv"
    table_path.write_text("time,value\n0,1\n1,2\n", encoding="utf-8")
    script_path = tmp_path / "plot_results.m"
    figure_path = tmp_path / "plot.png"

    result = await adapter.create_plot_export_script(
        table_path=str(table_path),
        x_column="time",
        y_column="value",
        output_script=str(script_path),
        output_figure=str(figure_path),
        title="Demo",
        kind="scatter",
    )

    script = script_path.read_text(encoding="utf-8")
    assert result["status"] == "ok"
    assert result["script_path"] == str(script_path.resolve())
    assert result["output_figure"] == str(figure_path.resolve())
    assert "readtable(" in script
    assert "scatter(x, y" in script
    assert "exportgraphics(fig" in script
    assert str(figure_path.resolve()) in script


@pytest.mark.asyncio
async def test_matlab_create_plot_export_script_rejects_unknown_kind(tmp_path):
    adapter = MatlabAdapter()
    table_path = tmp_path / "results.csv"
    table_path.write_text("x,y\n1,2\n", encoding="utf-8")

    with pytest.raises(ValueError, match="kind must be"):
        await adapter.create_plot_export_script(
            table_path=str(table_path),
            x_column="x",
            y_column="y",
            output_script=str(tmp_path / "plot_results.m"),
            output_figure=str(tmp_path / "plot.png"),
            kind="bar",
        )


@pytest.mark.asyncio
async def test_matlab_adapter_registered_on_server():
    server = ResearchMCPServer()

    await server.initialize({"matlab": {"matlab_cmd": "matlab"}})
    try:
        assert "matlab" in server._adapters
        assert "matlab_check_config" in server._tools
        assert "matlab_run_file" in server._tools
        assert "matlab_detect_toolboxes" in server._tools
        assert "matlab_parse_table" in server._tools
        assert "matlab_create_plot_export_script" in server._tools
    finally:
        await server.shutdown()


def test_matlab_capability_catalog_entry():
    capability = get_capability("matlab-mcp-core-server")

    assert capability is not None
    assert capability["key"] == "matlab"
    assert "matlab_run_file" in capability["internal_tools"]
    assert "matlab_parse_table" in capability["internal_tools"]
    assert "matlab_create_plot_export_script" in capability["internal_tools"]
