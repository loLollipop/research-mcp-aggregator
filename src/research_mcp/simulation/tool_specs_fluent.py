"""Fluent simulation tool metadata."""

from __future__ import annotations

from typing import Any

from research_mcp.adapters import ToolSpec


def build_fluent_tools(adapter: Any) -> list[ToolSpec]:
    return [
ToolSpec(
            name="fluent_run_journal",
            description="Run ANSYS Fluent in batch mode with a journal file.",
            input_schema={
                "type": "object",
                "properties": {
                    "journal_file": {
                        "type": "string",
                        "description": "Path to Fluent .jou journal file",
                        "minLength": 1,
                    },
                    "working_dir": {"type": "string", "description": "Working directory"},
                    "dimension": {"type": "string", "enum": ["2d", "3d"], "default": "3d"},
                    "precision": {"type": "string", "enum": ["sp", "dp"], "default": "dp"},
                    "processors": {
                        "type": "integer",
                        "description": "Parallel processor count",
                        "default": 1,
                        "minimum": 1,
                    },
                    "extra_args": {
                        "type": "string",
                        "description": "Additional command-line args",
                    },
                    "timeout_seconds": {
                        "type": "integer",
                        "description": "Timeout seconds",
                        "minimum": 1,
                    },
                },
                "required": ["journal_file"],
            },
            handler=adapter.fluent_run_journal,
        ),
        ToolSpec(
            name="fluent_parse_residuals",
            description="Parse Fluent residual history and assess convergence.",
            input_schema={
                "type": "object",
                "properties": {
                    "residual_file": {
                        "type": "string",
                        "description": "CSV or whitespace residual file",
                        "minLength": 1,
                    },
                    "threshold": {
                        "type": "number",
                        "description": "Convergence threshold",
                        "default": 1e-4,
                    },
                    "output_plot": {
                        "type": "string",
                        "description": "Optional SVG/PNG/PDF plot path",
                    },
                },
                "required": ["residual_file"],
            },
            handler=adapter.fluent_parse_residuals,
        ),
        ToolSpec(
            name="fluent_check_pyfluent",
            description="Check local PyFluent availability for live Fluent control.",
            input_schema={"type": "object", "properties": {}},
            handler=adapter.fluent_check_pyfluent,
        ),
        ToolSpec(
            name="fluent_launch_session",
            description="Launch a local Ansys Fluent solver session through PyFluent.",
            input_schema={
                "type": "object",
                "properties": {
                    "precision": {
                        "type": "string",
                        "enum": ["single", "double"],
                        "default": "double",
                    },
                    "dimension": {"type": "string", "enum": ["2d", "3d"], "default": "3d"},
                    "processor_count": {"type": "integer", "default": 1, "minimum": 1},
                    "working_directory": {
                        "type": "string",
                        "description": "Optional workdir",
                    },
                    "fluent_path": {
                        "type": "string",
                        "description": (
                            "Optional explicit Fluent executable path for PyFluent launch"
                        ),
                    },
                },
            },
            handler=adapter.fluent_launch_session,
        ),
        ToolSpec(
            name="fluent_inspect_file",
            description="Inspect Fluent case, data, or journal file metadata.",
            input_schema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to Fluent file",
                        "minLength": 1,
                    },
                    "preview_chars": {
                        "type": "integer",
                        "description": "Journal preview length",
                        "default": 1000,
                        "minimum": 1,
                    },
                },
                "required": ["file_path"],
            },
            handler=adapter.fluent_inspect_file,
        ),
        ToolSpec(
            name="fluent_list_sessions",
            description="List live Fluent sessions launched by this MCP process.",
            input_schema={"type": "object", "properties": {}},
            handler=adapter.fluent_list_sessions,
        ),
        ToolSpec(
            name="fluent_execute_tui",
            description="Execute Fluent TUI commands in a live PyFluent session.",
            input_schema={
                "type": "object",
                "properties": {
                    "session_id": {
                        "type": "string",
                        "description": "Fluent session id",
                        "minLength": 1,
                    },
                    "commands": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Fluent TUI commands",
                        "minItems": 1,
                    },
                },
                "required": ["session_id", "commands"],
            },
            handler=adapter.fluent_execute_tui,
        ),
        ToolSpec(
            name="fluent_close_session",
            description="Close a live Fluent session launched by this MCP process.",
            input_schema={
                "type": "object",
                "properties": {
                    "session_id": {
                        "type": "string",
                        "description": "Fluent session id",
                        "minLength": 1,
                    },
                },
                "required": ["session_id"],
            },
            handler=adapter.fluent_close_session,
        ),
    ]
