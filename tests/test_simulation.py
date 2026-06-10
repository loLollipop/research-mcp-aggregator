"""Tests for the simulation adapter."""

import os
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from research_mcp.adapters.simulation_adapter import SimulationAdapter
from research_mcp.server import ResearchMCPServer

EXPECTED_SIMULATION_TOOL_NAMES = {
    "simulation_check_config",
    "simulation_workflow_template",
    "comsol_check_mph",
    "comsol_server_connect",
    "comsol_server_disconnect",
    "comsol_server_info",
    "comsol_model_load",
    "comsol_model_create",
    "comsol_get_parameters",
    "comsol_set_parameters",
    "comsol_solve",
    "comsol_solve_status",
    "comsol_list_studies",
    "comsol_inspect_file",
    "comsol_run_batch",
    "comsol_parse_table",
    "fluent_check_pyfluent",
    "fluent_launch_session",
    "fluent_inspect_file",
    "fluent_list_sessions",
    "fluent_execute_tui",
    "fluent_close_session",
    "fluent_run_journal",
    "fluent_parse_residuals",
    "pfc_run_script",
    "pfc_parse_history",
    "pfc_bridge_status",
    "pfc_execute_code",
    "pfc_execute_task",
    "pfc_check_task_status",
    "pfc_list_tasks",
    "pfc_interrupt_task",
}


@pytest.mark.asyncio
async def test_simulation_metadata_tool_names_match_public_contract():
    adapter = SimulationAdapter()
    await adapter.initialize({})

    tool_names = [tool.name for tool in adapter.metadata().tools]

    assert set(tool_names) == EXPECTED_SIMULATION_TOOL_NAMES
    assert len(tool_names) == len(EXPECTED_SIMULATION_TOOL_NAMES)
    assert not any("__" in name for name in tool_names)


@pytest.mark.asyncio
async def test_simulation_config_defaults():
    adapter = SimulationAdapter()
    await adapter.initialize({})
    status = await adapter.check_config()
    assert status["comsol_cmd"] == "comsol"
    assert status["fluent_cmd"] == "fluent"
    assert status["pfc_cmd"] == "pfc"
    assert status["commands"] == {"comsol": "comsol", "fluent": "fluent", "pfc": "pfc"}
    assert status["scope_notice"]["role"] == "assistant_control_surface_for_existing_local_solvers"
    assert status["scope_notice"]["validation_scope"] == "not_solver_or_physics_validation"
    assert status["pfc_bridge"]["bridge_url"] == "ws://localhost:9001"
    assert set(status["optional_backends"]) == {"mph", "pyfluent", "websockets"}


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
    assert result["scope_notice"]["role"] == "assistant_control_surface_for_existing_local_solvers"
    assert result["scope_notice"]["requires_user_review"] is True
    assert any("dry_run=true" in step for step in result["steps"])
    assert "boundary and initial conditions" in result["user_validation_checklist"]


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
    assert result["assessment_scope"] == "final residuals compared with threshold only"
    assert (
        result["validation_scope"]
        == "not solver convergence certification or physics validation"
    )
    assert result["scope_notice"]["requires_user_review"] is True
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
async def test_fluent_launch_session_passes_explicit_executable_path(tmp_path):
    adapter = SimulationAdapter()
    fluent_exe = tmp_path / "ANSYS Inc" / "fluent.exe"
    fluent_exe.parent.mkdir()
    fluent_exe.write_text("stub", encoding="utf-8")
    await adapter.initialize({"fluent_cmd": str(fluent_exe)})
    launch_kwargs = {}
    session = SimpleNamespace(tui=SimpleNamespace(execute_command=lambda command: f"ok:{command}"))

    def launch_fluent(
        precision=None,
        dimension=None,
        mode=None,
        fluent_path=None,
        **kwargs,
    ):
        kwargs.update(
            precision=precision,
            dimension=dimension,
            mode=mode,
            fluent_path=fluent_path,
        )
        launch_kwargs.update(kwargs)
        return session

    pyfluent = SimpleNamespace(launch_fluent=launch_fluent)

    with patch(
        "research_mcp.simulation.fluent_backend.importlib.import_module",
        return_value=pyfluent,
    ):
        result = await adapter.fluent_launch_session()

    assert result["status"] == "ok"
    assert launch_kwargs["dimension"] == 3
    assert launch_kwargs["fluent_path"] == str(fluent_exe.resolve())


@pytest.mark.asyncio
async def test_fluent_launch_session_uses_version_for_pyfluent_without_dimension(tmp_path):
    adapter = SimulationAdapter()
    fluent_exe = tmp_path / "ANSYS Inc" / "v221" / "fluent" / "ntbin" / "win64" / "fluent.exe"
    fluent_exe.parent.mkdir(parents=True)
    fluent_exe.write_text("stub", encoding="utf-8")
    await adapter.initialize({"fluent_cmd": str(fluent_exe)})
    launch_kwargs = {}
    env_roots: list[str | None] = []
    old_root = os.environ.get("PYFLUENT_FLUENT_ROOT")
    session = SimpleNamespace(tui=SimpleNamespace(execute_command=lambda command: f"ok:{command}"))

    def launch_fluent(
        product_version=None,
        version=None,
        precision=None,
        processor_count=None,
        mode=None,
        cwd=None,
        **kwargs,
    ):
        assert kwargs == {}
        env_roots.append(os.environ.get("PYFLUENT_FLUENT_ROOT"))
        launch_kwargs.update(
            product_version=product_version,
            version=version,
            precision=precision,
            processor_count=processor_count,
            mode=mode,
            cwd=cwd,
        )
        return session

    pyfluent = SimpleNamespace(launch_fluent=launch_fluent)

    with patch(
        "research_mcp.simulation.fluent_backend.importlib.import_module",
        return_value=pyfluent,
    ):
        result = await adapter.fluent_launch_session(processor_count=1)

    assert result["status"] == "ok"
    assert launch_kwargs["version"] == "3d"
    assert launch_kwargs["processor_count"] == 1
    assert env_roots == [str((tmp_path / "ANSYS Inc" / "v221" / "fluent").resolve())]
    assert os.environ.get("PYFLUENT_FLUENT_ROOT") == old_root


@pytest.mark.asyncio
async def test_fluent_launch_session_rejects_missing_working_directory(tmp_path):
    adapter = SimulationAdapter()
    await adapter.initialize({})
    pyfluent = SimpleNamespace(launch_fluent=lambda **kwargs: object())

    with patch(
        "research_mcp.simulation.fluent_backend.importlib.import_module",
        return_value=pyfluent,
    ):
        with pytest.raises(FileNotFoundError, match="Working directory"):
            await adapter.fluent_launch_session(working_directory=str(tmp_path / "missing"))


@pytest.mark.asyncio
async def test_shutdown_closes_tracked_fluent_sessions():
    adapter = SimulationAdapter()
    await adapter.initialize({})
    closed: list[bool] = []
    session = SimpleNamespace(
        tui=SimpleNamespace(execute_command=lambda command: f"executed:{command}"),
        exit=lambda: closed.append(True),
    )
    pyfluent = SimpleNamespace(launch_fluent=lambda **kwargs: session)

    with patch(
        "research_mcp.simulation.fluent_backend.importlib.import_module",
        return_value=pyfluent,
    ):
        launch = await adapter.fluent_launch_session()

    assert launch["status"] == "ok"
    await adapter.shutdown()

    assert closed == [True]
    sessions = await adapter.fluent_list_sessions()
    assert sessions["count"] == 0


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
    assert result["source_independent_column"] == "step"
    assert result["summaries"]["crack_count"]["max"] == 5.0
    assert result["summaries"]["kinetic_energy"]["final"] == 4.0
    assert output_plot.exists()


@pytest.mark.asyncio
async def test_pfc_parse_history_accepts_units_comments_and_d_exponents(tmp_path):
    adapter = SimulationAdapter()
    await adapter.initialize({})
    history_file = tmp_path / "history.out"
    history_file.write_text(
        "step crack_count energy\n"
        "1 0 1.0D+1[J]\n"
        "bad nonnumeric row\n"
        "2 3 8.0[J] ; converged\n"
        "3 5 4.0[J]\n",
        encoding="utf-8",
    )

    result = await adapter.pfc_parse_history(str(history_file))

    assert result["rows"] == 3
    assert result["source_independent_column"] == "step"
    assert result["summaries"]["energy"]["final"] == 4.0
    assert (
        result["assessment_scope"]
        == "exported PFC history summary only; not DEM model validation"
    )
    assert result["scope_notice"]["validation_scope"] == "not_solver_or_physics_validation"


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
    assert (
        result["assessment_scope"]
        == "exported-table summary only; not solver or physics validation"
    )
    assert result["scope_notice"]["role"] == "assistant_control_surface_for_existing_local_solvers"
    assert output_plot.exists()


@pytest.mark.asyncio
async def test_comsol_parse_table_accepts_whitespace_units_and_inline_comments(tmp_path):
    adapter = SimulationAdapter()
    await adapter.initialize({})
    table_file = tmp_path / "comsol_table.txt"
    table_file.write_text(
        "% parameter temperature stress\n"
        "1[1]   300[K]   10[MPa]\n"
        "ignored row text\n"
        "2[1]   330[K]   15[MPa] # final row\n",
        encoding="utf-8",
    )

    result = await adapter.comsol_parse_table(str(table_file), x_column="parameter")

    assert result["rows"] == 2
    assert result["summaries"]["temperature"]["final"] == 330.0
    assert result["summaries"]["stress"]["max"] == 15.0


@pytest.mark.asyncio
async def test_simulation_rejects_invalid_executable_command():
    adapter = SimulationAdapter()

    with pytest.raises(ValueError, match="single executable"):
        await adapter.initialize({"comsol_cmd": "comsol --unsafe"})


@pytest.mark.asyncio
async def test_simulation_accepts_executable_paths_with_spaces(tmp_path):
    adapter = SimulationAdapter()
    executable = tmp_path / "Program Files" / "solver.exe"
    executable.parent.mkdir()
    executable.write_text("stub", encoding="utf-8")

    await adapter.initialize({"comsol_cmd": str(executable)})
    status = await adapter.check_config()

    assert status["comsol_cmd"] == str(executable.resolve())


@pytest.mark.asyncio
async def test_simulation_rejects_shell_like_extra_args(tmp_path):
    adapter = SimulationAdapter()
    await adapter.initialize({})
    model = tmp_path / "model.mph"
    model.write_text("model", encoding="utf-8")

    with patch(
        "research_mcp.adapters.simulation_adapter.run_command",
        side_effect=AssertionError("subprocess should not start"),
    ):
        with pytest.raises(ValueError, match="shell control"):
            await adapter.comsol_run_batch(str(model), extra_args="-np 2; rm -rf out")


@pytest.mark.asyncio
async def test_fluent_run_journal_rejects_invalid_working_dir(tmp_path):
    adapter = SimulationAdapter()
    await adapter.initialize({})
    journal = tmp_path / "run.jou"
    journal.write_text("/solve/iterate 1\n", encoding="utf-8")

    with pytest.raises(FileNotFoundError, match="Working directory"):
        await adapter.fluent_run_journal(str(journal), working_dir=str(tmp_path / "missing"))


@pytest.mark.asyncio
async def test_fluent_run_journal_dry_run_returns_command_without_execution(tmp_path):
    adapter = SimulationAdapter()
    await adapter.initialize({"fluent_cmd": "fluent"})
    journal = tmp_path / "run.jou"
    journal.write_text("/solve/iterate 1\n", encoding="utf-8")

    with patch(
        "research_mcp.adapters.simulation_adapter.run_command",
        side_effect=AssertionError("subprocess should not start"),
    ):
        result = await adapter.fluent_run_journal(
            str(journal),
            dimension="2d",
            precision="dp",
            processors=4,
            extra_args="-hidden",
            timeout_seconds=12,
            dry_run=True,
        )

    assert result["status"] == "dry_run"
    assert result["tool"] == "fluent_run_journal"
    assert result["command"] == [
        "fluent",
        "2ddp",
        "-g",
        "-i",
        str(journal.resolve()),
        "-t",
        "4",
        "-hidden",
    ]
    assert result["cwd"] == str(tmp_path.resolve())
    assert result["timeout_seconds"] == 12
    assert result["input_files"] == {"journal_file": str(journal.resolve())}


@pytest.mark.asyncio
async def test_comsol_run_batch_rejects_unsupported_output_suffix(tmp_path):
    adapter = SimulationAdapter()
    await adapter.initialize({})
    model = tmp_path / "model.mph"
    model.write_text("model", encoding="utf-8")

    with patch(
        "research_mcp.adapters.simulation_adapter.run_command",
        side_effect=AssertionError("subprocess should not start"),
    ):
        with pytest.raises(ValueError, match="Unsupported output suffix"):
            await adapter.comsol_run_batch(str(model), output_file="result.txt")


@pytest.mark.asyncio
async def test_comsol_run_batch_dry_run_returns_command_without_creating_output_dir(tmp_path):
    adapter = SimulationAdapter()
    await adapter.initialize({"comsol_cmd": "comsol", "timeout_seconds": 99})
    model = tmp_path / "model.mph"
    model.write_text("model", encoding="utf-8")
    output_file = tmp_path / "new" / "result.mph"

    with patch(
        "research_mcp.adapters.simulation_adapter.run_command",
        side_effect=AssertionError("subprocess should not start"),
    ):
        result = await adapter.comsol_run_batch(
            str(model),
            output_file=str(output_file),
            study="std1",
            extra_args="-np 2",
            dry_run=True,
        )

    assert result["status"] == "dry_run"
    assert result["tool"] == "comsol_run_batch"
    assert result["command"] == [
        "comsol",
        "batch",
        "-inputfile",
        str(model.resolve()),
        "-outputfile",
        str(output_file.resolve()),
        "-study",
        "std1",
        "-np",
        "2",
    ]
    assert result["timeout_seconds"] == 99
    assert result["input_files"] == {"model_file": str(model.resolve())}
    assert result["output_files"] == {"model_output": str(output_file.resolve())}
    assert result["scope_notice"]["requires_user_review"] is True
    assert not output_file.parent.exists()


@pytest.mark.asyncio
async def test_comsol_run_batch_supports_comsolbatch_executable(tmp_path):
    adapter = SimulationAdapter()
    comsolbatch = tmp_path / "Program Files" / "comsolbatch.exe"
    comsolbatch.parent.mkdir()
    comsolbatch.write_text("stub", encoding="utf-8")
    await adapter.initialize({"comsol_cmd": str(comsolbatch)})
    model = tmp_path / "model.mph"
    model.write_text("model", encoding="utf-8")

    async def fake_run_command(args, cwd, timeout_seconds):
        return {"args": args, "cwd": str(cwd), "timeout_seconds": timeout_seconds}

    with patch("research_mcp.adapters.simulation_adapter.run_command", fake_run_command):
        result = await adapter.comsol_run_batch(str(model), timeout_seconds=5)

    assert result["args"][:2] == [str(comsolbatch.resolve()), "-inputfile"]
    assert "batch" not in result["args"]


@pytest.mark.asyncio
async def test_parse_plot_rejects_unsupported_suffix_before_directory_creation(tmp_path):
    adapter = SimulationAdapter()
    await adapter.initialize({})
    residual_file = tmp_path / "residuals.csv"
    residual_file.write_text("iteration,continuity\n1,1e-2\n", encoding="utf-8")
    output_plot = tmp_path / "new" / "residuals.txt"

    with pytest.raises(ValueError, match="Unsupported output suffix"):
        await adapter.fluent_parse_residuals(str(residual_file), output_plot=str(output_plot))

    assert not output_plot.parent.exists()


@pytest.mark.asyncio
async def test_pfc_run_script_rejects_invalid_working_dir(tmp_path):
    adapter = SimulationAdapter()
    await adapter.initialize({})
    script = tmp_path / "run.p3dat"
    script.write_text("model new\n", encoding="utf-8")

    with pytest.raises(FileNotFoundError, match="Working directory"):
        await adapter.pfc_run_script(str(script), working_dir=str(tmp_path / "missing"))


@pytest.mark.asyncio
async def test_pfc_run_script_dry_run_returns_command_without_execution(tmp_path):
    adapter = SimulationAdapter()
    await adapter.initialize({"pfc_cmd": "pfc"})
    script = tmp_path / "run.p3dat"
    script.write_text("model new\n", encoding="utf-8")

    with patch(
        "research_mcp.adapters.simulation_adapter.run_command",
        side_effect=AssertionError("subprocess should not start"),
    ):
        result = await adapter.pfc_run_script(
            str(script),
            extra_args="--console",
            timeout_seconds=7,
            dry_run=True,
        )

    assert result["status"] == "dry_run"
    assert result["tool"] == "pfc_run_script"
    assert result["command"] == ["pfc", str(script.resolve()), "--console"]
    assert result["cwd"] == str(tmp_path.resolve())
    assert result["timeout_seconds"] == 7
    assert result["input_files"] == {"script_file": str(script.resolve())}


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
