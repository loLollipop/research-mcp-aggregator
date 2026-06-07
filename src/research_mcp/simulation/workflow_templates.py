"""Workflow templates for simulation studies."""

from __future__ import annotations

from typing import Any

DEFAULT_PARAMETERS = [
    "primary_control_parameter",
    "mesh_or_particle_resolution",
    "boundary_condition",
]

SOLVER_TOOLS = {
    "comsol": [
        "comsol_check_mph",
        "comsol_server_connect",
        "comsol_model_load",
        "comsol_get_parameters",
        "comsol_set_parameters",
        "comsol_solve",
        "comsol_run_batch",
        "comsol_parse_table",
    ],
    "fluent": [
        "fluent_check_pyfluent",
        "fluent_launch_session",
        "fluent_inspect_file",
        "fluent_execute_tui",
        "fluent_close_session",
        "fluent_run_journal",
        "fluent_parse_residuals",
    ],
    "pfc": [
        "pfc_run_script",
        "pfc_parse_history",
        "pfc_bridge_status",
        "pfc_execute_code",
        "pfc_execute_task",
        "pfc_check_task_status",
        "pfc_list_tasks",
        "pfc_interrupt_task",
    ],
    "mixed": ["comsol_run_batch", "fluent_run_journal", "pfc_run_script"],
}


def build_workflow_template(
    solver: str = "mixed",
    objective: str = "engineering simulation study",
    parameters: list[str] | None = None,
) -> dict[str, Any]:
    solver_tools = SOLVER_TOOLS.get(solver, SOLVER_TOOLS["mixed"])
    return {
        "solver": solver,
        "objective": objective,
        "local_tools": ["simulation_check_config", *solver_tools],
        "parameters": parameters or DEFAULT_PARAMETERS,
        "steps": [
            "Record solver version, command path, license environment, and workdir.",
            "Create one input file per parameter point or a generator script.",
            "Run the configured local solver command through research-mcp.",
            "Save stdout, stderr, return code, raw outputs, and configuration.",
            "Post-process numeric outputs with plot_csv_columns or plot_xy.",
        ],
        "recommended_outputs": [
            "resolved_parameters.csv",
            "solver_stdout.log",
            "solver_stderr.log",
            "raw_results/",
            "figures/",
        ],
    }
