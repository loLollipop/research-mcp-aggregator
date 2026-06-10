"""COMSOL simulation tool metadata."""

from __future__ import annotations

from typing import Any

from research_mcp.adapters import ToolSpec


def build_comsol_tools(adapter: Any) -> list[ToolSpec]:
    return [
        ToolSpec(
            name="comsol_run_batch",
            description=(
                "Run or dry-run an existing COMSOL .mph model through the configured "
                "local COMSOL batch command."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "model_file": {
                        "type": "string",
                        "description": "Path to input .mph model",
                        "minLength": 1,
                    },
                    "output_file": {
                        "type": "string",
                        "description": "Optional output .mph path",
                    },
                    "study": {
                        "type": "string",
                        "description": "Optional COMSOL study tag/name",
                    },
                    "extra_args": {
                        "type": "string",
                        "description": "Additional command-line args",
                    },
                    "timeout_seconds": {
                        "type": "integer",
                        "description": "Timeout seconds",
                        "minimum": 1,
                        "maximum": 86400,
                    },
                    "dry_run": {
                        "type": "boolean",
                        "description": "Return resolved command metadata without launching COMSOL",
                        "default": False,
                    },
                },
                "required": ["model_file"],
            },
            handler=adapter.comsol_run_batch,
        ),
        ToolSpec(
            name="comsol_parse_table",
            description="Parse a COMSOL exported table and summarize result columns.",
            input_schema={
                "type": "object",
                "properties": {
                    "table_file": {
                        "type": "string",
                        "description": "CSV or text table exported from COMSOL",
                        "minLength": 1,
                    },
                    "x_column": {
                        "type": "string",
                        "description": "Optional x/parameter column for plotting",
                    },
                    "output_plot": {
                        "type": "string",
                        "description": "Optional SVG/PNG/PDF plot path",
                    },
                },
                "required": ["table_file"],
            },
            handler=adapter.comsol_parse_table,
        ),
        ToolSpec(
            name="comsol_check_mph",
            description="Check whether the MPh library is available.",
            input_schema={"type": "object", "properties": {}},
            handler=adapter.comsol_check_mph,
        ),
        ToolSpec(
            name="comsol_server_connect",
            description="Connect to a running COMSOL Multiphysics Server (attach-first pattern).",
            input_schema={
                "type": "object",
                "properties": {
                    "host": {"type": "string", "default": "localhost"},
                    "port": {"type": "integer", "default": 2036, "minimum": 1, "maximum": 65535},
                    "model_path": {
                        "type": "string",
                        "description": "Optional .mph file to load after connecting",
                    },
                    "timeout_seconds": {
                        "type": "number",
                        "default": 30.0,
                        "minimum": 1,
                        "maximum": 600,
                    },
                },
            },
            handler=adapter.comsol_server_connect,
        ),
        ToolSpec(
            name="comsol_server_disconnect",
            description="Disconnect from the COMSOL Server and release resources.",
            input_schema={"type": "object", "properties": {}},
            handler=adapter.comsol_server_disconnect,
        ),
        ToolSpec(
            name="comsol_server_info",
            description="Show COMSOL connection and model status.",
            input_schema={"type": "object", "properties": {}},
            handler=adapter.comsol_server_info,
        ),
        ToolSpec(
            name="comsol_model_load",
            description="Load a .mph model file on the connected COMSOL Server.",
            input_schema={
                "type": "object",
                "properties": {
                    "model_path": {
                        "type": "string",
                        "description": "Path to .mph model file",
                        "minLength": 1,
                    },
                },
                "required": ["model_path"],
            },
            handler=adapter.comsol_model_load,
        ),
        ToolSpec(
            name="comsol_model_create",
            description="Create a new empty model on the connected COMSOL Server.",
            input_schema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "default": "Server Model"},
                },
            },
            handler=adapter.comsol_model_create,
        ),
        ToolSpec(
            name="comsol_get_parameters",
            description="Read global parameters from the current COMSOL model.",
            input_schema={"type": "object", "properties": {}},
            handler=adapter.comsol_get_parameters,
        ),
        ToolSpec(
            name="comsol_set_parameters",
            description="Set global parameters on the current COMSOL model.",
            input_schema={
                "type": "object",
                "properties": {
                    "parameters": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string", "minLength": 1},
                                "expression": {"type": "string", "minLength": 1},
                            },
                            "required": ["name", "expression"],
                        },
                        "description": ' [{"name":"p","expression":"1.5"}]',
                        "minItems": 1,
                        "maxItems": 1000,
                    },
                },
                "required": ["parameters"],
            },
            handler=adapter.comsol_set_parameters,
        ),
        ToolSpec(
            name="comsol_solve",
            description=(
                "Request COMSOL to solve the current model; setup and validation remain "
                "in COMSOL/user workflow."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "study_tag": {
                        "type": "string",
                        "description": "Optional study tag",
                        "default": "",
                    },
                    "async_mode": {
                        "type": "boolean",
                        "description": "Run in background thread",
                        "default": False,
                    },
                },
            },
            handler=adapter.comsol_solve,
        ),
        ToolSpec(
            name="comsol_solve_status",
            description="Poll status of a background COMSOL solve job.",
            input_schema={
                "type": "object",
                "properties": {
                    "job_id": {
                        "type": "string",
                        "description": "Job id from comsol_solve async",
                        "default": "",
                    },
                },
            },
            handler=adapter.comsol_solve_status,
        ),
        ToolSpec(
            name="comsol_list_studies",
            description="List study tags in the current COMSOL model.",
            input_schema={"type": "object", "properties": {}},
            handler=adapter.comsol_list_studies,
        ),
        ToolSpec(
            name="comsol_inspect_file",
            description="Inspect a COMSOL-related file for metadata and preview.",
            input_schema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to COMSOL file",
                        "minLength": 1,
                    },
                    "preview_chars": {
                        "type": "integer",
                        "description": "Preview length",
                        "default": 1000,
                        "minimum": 1,
                        "maximum": 200000,
                    },
                },
                "required": ["file_path"],
            },
            handler=adapter.comsol_inspect_file,
        ),
    ]
