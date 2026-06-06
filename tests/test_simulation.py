"""Tests for the simulation adapter."""

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from research_mcp.adapters.simulation_adapter import SimulationAdapter
from research_mcp.server import ResearchMCPServer


@pytest.mark.asyncio
async def test_simulation_config_defaults():
    adapter = SimulationAdapter()
    await adapter.initialize({})
    status = await adapter.check_config()
    assert status["comsol_cmd"] == "comsol"
    assert status["fluent_cmd"] == "fluent"
    assert status["pfc_cmd"] == "pfc"


@pytest.mark.asyncio
async def test_simulation_config_override():
    adapter = SimulationAdapter()
    await adapter.initialize({"comsol_cmd": "comsol.exe", "timeout_seconds": 10})
    status = await adapter.check_config()
    assert status["comsol_cmd"] == "comsol.exe"
    assert status["timeout_seconds"] == 10


@pytest.mark.asyncio
async def test_simulation_workflow_template_uses_local_tools():
    adapter = SimulationAdapter()
    await adapter.initialize({})
    result = await adapter.workflow_template(
        "pfc", "rock breaking", ["water_pressure", "laser_power"]
    )
    assert result["solver"] == "pfc"
    assert "pfc_run_script" in result["local_tools"]


@pytest.mark.asyncio
async def test_fluent_parse_residuals_csv(tmp_path):
    adapter = SimulationAdapter()
    await adapter.initialize({})
    residual_file = tmp_path / "residuals.csv"
    residual_file.write_text(
        "iteration,continuity,x-velocity,energy\n1,1e-2,2e-2,5e-5\n2,1e-5,2e-5,1e-6\n",
        encoding="utf-8",
    )
    output_plot = tmp_path / "residuals.svg"

    result = await adapter.fluent_parse_residuals(
        str(residual_file), threshold=1e-4, output_plot=str(output_plot)
    )

    assert result["iterations"] == 2
    assert result["converged"] is True
    assert result["final_residuals"]["continuity"] == 1e-5
    assert output_plot.exists()


@pytest.mark.asyncio
async def test_fluent_parse_residuals_without_header(tmp_path):
    adapter = SimulationAdapter()
    await adapter.initialize({})
    residual_file = tmp_path / "residuals.out"
    residual_file.write_text("1 1e-2 2e-2\n2 1e-3 2e-3\n", encoding="utf-8")

    result = await adapter.fluent_parse_residuals(str(residual_file), threshold=1e-4)

    assert result["iterations"] == 2
    assert result["converged"] is False


@pytest.mark.asyncio
async def test_fluent_inspect_file_classifies_case_and_data_files(tmp_path):
    adapter = SimulationAdapter()
    await adapter.initialize({})
    case = tmp_path / "model.cas.h5"
    data = tmp_path / "result.dat.h5"
    case.write_text("case", encoding="utf-8")
    data.write_text("data", encoding="utf-8")

    case_result = await adapter.fluent_inspect_file(str(case))
    data_result = await adapter.fluent_inspect_file(str(data))

    assert case_result["file_info"]["extension"] == ".cas.h5"
    assert case_result["file_info"]["type"] == "Fluent case file"
    assert data_result["file_info"]["extension"] == ".dat.h5"
    assert data_result["file_info"]["type"] == "Fluent data file"


@pytest.mark.asyncio
async def test_simulation_server_registers_fluent_tools_without_proxy_names():
    server = ResearchMCPServer()
    await server.initialize({})
    try:
        tool_names = set(server._tools)
    finally:
        await server.shutdown()

    assert "fluent_check_pyfluent" in tool_names
    assert "fluent_launch_session" in tool_names
    assert "fluent_inspect_file" in tool_names
    assert "fluent_list_sessions" in tool_names
    assert "fluent_execute_tui" in tool_names
    assert "fluent_close_session" in tool_names
    assert "fluent_run_journal" in tool_names
    assert "fluent_parse_residuals" in tool_names
    assert "mcp_bridge_status" not in tool_names
    assert not any("__" in name for name in tool_names)


@pytest.mark.asyncio
async def test_fluent_check_pyfluent_not_found():
    adapter = SimulationAdapter()
    await adapter.initialize({})

    with patch(
        "research_mcp.simulation.fluent_backend.importlib.import_module",
        side_effect=ImportError,
    ):
        result = await adapter.fluent_check_pyfluent()

    assert result["status"] == "not_found"
    assert result["module"] == "ansys.fluent.core"


@pytest.mark.asyncio
async def test_fluent_check_pyfluent_available():
    adapter = SimulationAdapter()
    await adapter.initialize({})
    module = SimpleNamespace(__version__="1.2.3")

    with patch(
        "research_mcp.simulation.fluent_backend.importlib.import_module",
        return_value=module,
    ):
        result = await adapter.fluent_check_pyfluent()

    assert result["status"] == "available"
    assert result["version"] == "1.2.3"


@pytest.mark.asyncio
async def test_fluent_inspect_file_journal(tmp_path):
    adapter = SimulationAdapter()
    await adapter.initialize({})
    journal = tmp_path / "run.jou"
    journal.write_text("/solve/iterate 10\n/file/write-data out.dat\n", encoding="utf-8")

    result = await adapter.fluent_inspect_file(str(journal), preview_chars=20)

    assert result["status"] == "ok"
    assert result["file_info"]["type"] == "Fluent journal file"
    assert result["file_info"]["preview"] == "/solve/iterate 10\n/f"


@pytest.mark.asyncio
async def test_fluent_launch_session_with_mock_pyfluent():
    adapter = SimulationAdapter()
    await adapter.initialize({})
    session = SimpleNamespace(tui=SimpleNamespace(execute_command=lambda command: f"ok:{command}"))
    pyfluent = SimpleNamespace(launch_fluent=lambda **kwargs: session)

    with patch(
        "research_mcp.simulation.fluent_backend.importlib.import_module",
        return_value=pyfluent,
    ):
        result = await adapter.fluent_launch_session(
            precision="double", dimension="3d", processor_count=2
        )

    assert result["status"] == "ok"
    assert result["processor_count"] == 2
    sessions = await adapter.fluent_list_sessions()
    assert sessions["count"] == 1


@pytest.mark.asyncio
async def test_fluent_execute_tui_and_close_session_with_mock_pyfluent():
    adapter = SimulationAdapter()
    await adapter.initialize({})
    session = SimpleNamespace(
        tui=SimpleNamespace(execute_command=lambda command: f"executed:{command}"),
        exit=lambda: None,
    )
    pyfluent = SimpleNamespace(launch_fluent=lambda **kwargs: session)

    with patch(
        "research_mcp.simulation.fluent_backend.importlib.import_module",
        return_value=pyfluent,
    ):
        launch = await adapter.fluent_launch_session()

    result = await adapter.fluent_execute_tui(
        launch["session_id"], ["# comment", "", "/solve/iterate 5"]
    )
    closed = await adapter.fluent_close_session(launch["session_id"])

    assert result["status"] == "ok"
    assert result["commands_executed"] == 1
    assert result["results"][0]["output"] == "executed:/solve/iterate 5"
    assert closed["closed"] is True


@pytest.mark.asyncio
async def test_fluent_execute_tui_missing_session():
    adapter = SimulationAdapter()
    await adapter.initialize({})

    result = await adapter.fluent_execute_tui("missing", ["/solve/iterate 5"])

    assert result["status"] == "not_found"


@pytest.mark.asyncio
async def test_pfc_parse_history_summarizes_series(tmp_path):
    adapter = SimulationAdapter()
    await adapter.initialize({})
    history_file = tmp_path / "history.csv"
    history_file.write_text(
        "step,crack_count,kinetic_energy\n1,0,10.0\n2,3,8.0\n3,5,4.0\n",
        encoding="utf-8",
    )
    output_plot = tmp_path / "history.svg"

    result = await adapter.pfc_parse_history(str(history_file), str(output_plot))

    assert result["rows"] == 3
    assert result["independent_column"] == "iteration"
    assert result["summaries"]["crack_count"]["max"] == 5.0
    assert result["summaries"]["kinetic_energy"]["final"] == 4.0
    assert output_plot.exists()


@pytest.mark.asyncio
async def test_comsol_parse_table_summarizes_exported_table(tmp_path):
    adapter = SimulationAdapter()
    await adapter.initialize({})
    table_file = tmp_path / "comsol_table.csv"
    table_file.write_text(
        "% parameter,temperature,stress\n1,300.0,10.0\n2,330.0,15.0\n3,360.0,12.0\n",
        encoding="utf-8",
    )
    output_plot = tmp_path / "comsol_table.svg"

    result = await adapter.comsol_parse_table(
        str(table_file), x_column="parameter", output_plot=str(output_plot)
    )

    assert result["rows"] == 3
    assert result["x_column"] == "parameter"
    assert result["summaries"]["temperature"]["max"] == 360.0
    assert result["summaries"]["stress"]["mean"] == pytest.approx(12.3333333333)
    assert output_plot.exists()


# ------------------------------------------------------------------
# COMSOL MPh backend tests (mock-based, no real COMSOL needed)
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_comsol_check_mph_not_found():
    adapter = SimulationAdapter()
    await adapter.initialize({})

    with patch(
        "research_mcp.simulation.comsol_backend.importlib.import_module",
        side_effect=ImportError,
    ):
        result = await adapter.comsol_check_mph()

    assert result["status"] == "not_found"
    assert result["module"] == "mph"


@pytest.mark.asyncio
async def test_comsol_check_mph_available():
    adapter = SimulationAdapter()
    await adapter.initialize({})
    mph_mod = SimpleNamespace(__version__="1.2.0")

    with patch(
        "research_mcp.simulation.comsol_backend.importlib.import_module",
        return_value=mph_mod,
    ):
        result = await adapter.comsol_check_mph()

    assert result["status"] == "available"
    assert result["version"] == "1.2.0"
    assert result["connected"] is False


@pytest.mark.asyncio
async def test_comsol_server_connect_and_disconnect():
    adapter = SimulationAdapter()
    await adapter.initialize({})

    fake_client = SimpleNamespace(
        connect=lambda port, host: None,
        disconnect=lambda: None,
        models=lambda: [],
    )
    fake_mph = SimpleNamespace(
        Client=lambda host=None: fake_client,
        __version__="1.3.0",
    )

    with patch(
        "research_mcp.simulation.comsol_backend.importlib.import_module",
        return_value=fake_mph,
    ):
        connect_result = await adapter.comsol_server_connect(port=2036)

    assert connect_result["status"] == "ok"
    assert connect_result["connected"] is True

    info = await adapter.comsol_server_info()
    assert info["connected"] is True
    assert info["port"] == 2036

    disconnect_result = await adapter.comsol_server_disconnect()
    assert disconnect_result["status"] == "ok"
    assert disconnect_result["connected"] is False


@pytest.mark.asyncio
async def test_comsol_model_load_and_get_parameters():
    adapter = SimulationAdapter()
    await adapter.initialize({})
    fake_param = SimpleNamespace(
        varnames=lambda: ["p1", "p2"],
        get=lambda name: "1.5" if name == "p1" else "2.0",
    )
    fake_java = SimpleNamespace(param=lambda: fake_param)
    fake_model = SimpleNamespace(java=fake_java, name=lambda: "test.mph")

    fake_client = SimpleNamespace(
        connect=lambda port, host: None,
        disconnect=lambda: None,
        models=lambda: [],
        load=lambda path: fake_model,
    )
    fake_mph = SimpleNamespace(Client=lambda host=None: fake_client)

    with patch(
        "research_mcp.simulation.comsol_backend.importlib.import_module",
        return_value=fake_mph,
    ):
        tmp_model = adapter._comsol_backend  # access backend directly
        # manually set connected state for testing
        tmp_model._connected = True
        tmp_model._client = fake_client

    # create a temporary .mph file
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".mph", delete=False) as f:
        mph_path = f.name

    try:
        load_result = await adapter.comsol_model_load(mph_path)
        assert load_result["status"] == "ok"
        assert "model_label" in load_result

        params = await adapter.comsol_get_parameters()
        assert params["status"] == "ok"
        assert params["count"] == 2
        assert params["parameters"][0]["name"] == "p1"
    finally:
        import os

        os.unlink(mph_path)
        # cleanup
        adapter._comsol_backend._connected = False
        adapter._comsol_backend._client = None
        adapter._comsol_backend._model = None


@pytest.mark.asyncio
async def test_comsol_set_parameters():
    adapter = SimulationAdapter()
    await adapter.initialize({})

    set_calls: list[tuple[str, str]] = []
    fake_param = SimpleNamespace(
        varnames=lambda: ["p1"],
        get=lambda name: "1.0",
        set=lambda name, expr: set_calls.append((name, expr)),
    )
    fake_java = SimpleNamespace(param=lambda: fake_param)
    fake_model = SimpleNamespace(java=fake_java)

    # manually set backend state
    adapter._comsol_backend._connected = True
    adapter._comsol_backend._model = fake_model
    adapter._comsol_backend._model_label = "test"

    result = await adapter.comsol_set_parameters([{"name": "p1", "expression": "3.0"}])

    assert result["status"] == "ok"
    assert result["count"] == 1
    assert set_calls == [("p1", "3.0")]

    # cleanup
    adapter._comsol_backend._connected = False
    adapter._comsol_backend._client = None
    adapter._comsol_backend._model = None


@pytest.mark.asyncio
async def test_comsol_solve_sync():
    adapter = SimulationAdapter()
    await adapter.initialize({})

    solve_called_with: list[str] = []
    fake_java = SimpleNamespace(
        study=lambda: SimpleNamespace(
            get=lambda tag: SimpleNamespace(label=lambda: "Study 1"),
        ),
    )
    fake_model = SimpleNamespace(
        java=fake_java,
        solve=lambda label_or_tag="": solve_called_with.append(str(label_or_tag)),
    )

    adapter._comsol_backend._connected = True
    adapter._comsol_backend._model = fake_model
    adapter._comsol_backend._model_label = "test"

    result = await adapter.comsol_solve(study_tag="std1")
    assert result["status"] == "ok"
    assert result["study_tag"] == "std1"
    assert "Study 1" in solve_called_with

    # cleanup
    adapter._comsol_backend._connected = False
    adapter._comsol_backend._client = None
    adapter._comsol_backend._model = None


@pytest.mark.asyncio
async def test_comsol_solve_async_poll():
    adapter = SimulationAdapter()
    await adapter.initialize({})

    fake_java = SimpleNamespace(
        study=lambda: SimpleNamespace(
            get=lambda tag: SimpleNamespace(label=lambda: "Study 1"),
        ),
    )
    fake_model = SimpleNamespace(
        java=fake_java,
        solve=lambda label_or_tag="": None,
    )

    adapter._comsol_backend._connected = True
    adapter._comsol_backend._model = fake_model
    adapter._comsol_backend._model_label = "test"

    start = await adapter.comsol_solve(study_tag="std1", async_mode=True)
    assert start["status"] == "ok"
    assert "job_id" in start

    import time

    time.sleep(0.3)

    status = await adapter.comsol_solve_status(start["job_id"])
    assert status["status"] == "ok"
    assert status["job"]["status"] == "succeeded"

    # cleanup
    adapter._comsol_backend._connected = False
    adapter._comsol_backend._client = None
    adapter._comsol_backend._model = None
    adapter._comsol_backend._jobs.clear()


@pytest.mark.asyncio
async def test_comsol_inspect_file(tmp_path):
    adapter = SimulationAdapter()
    await adapter.initialize({})
    mph = tmp_path / "model.mph"
    mph.write_bytes(b"fake mph")
    csv = tmp_path / "results.csv"
    csv.write_text("% col1,col2\n1,2\n", encoding="utf-8")

    mph_result = await adapter.comsol_inspect_file(str(mph))
    assert mph_result["status"] == "ok"
    assert mph_result["file_info"]["type"] == "COMSOL model file"

    csv_result = await adapter.comsol_inspect_file(str(csv), preview_chars=20)
    assert csv_result["status"] == "ok"
    assert "preview" in csv_result["file_info"]


@pytest.mark.asyncio
async def test_simulation_server_registers_comsol_tools():
    server = ResearchMCPServer()
    await server.initialize({})
    try:
        tool_names = set(server._tools)
    finally:
        await server.shutdown()

    assert "comsol_check_mph" in tool_names
    assert "comsol_server_connect" in tool_names
    assert "comsol_server_disconnect" in tool_names
    assert "comsol_server_info" in tool_names
    assert "comsol_model_load" in tool_names
    assert "comsol_model_create" in tool_names
    assert "comsol_get_parameters" in tool_names
    assert "comsol_set_parameters" in tool_names
    assert "comsol_solve" in tool_names
    assert "comsol_solve_status" in tool_names
    assert "comsol_list_studies" in tool_names
    assert "comsol_inspect_file" in tool_names
    assert "comsol_run_batch" in tool_names
    assert "comsol_parse_table" in tool_names
    assert "mcp_bridge_status" not in tool_names
    assert not any("__" in name for name in tool_names)
