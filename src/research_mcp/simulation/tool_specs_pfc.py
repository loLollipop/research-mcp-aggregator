"""PFC simulation tool metadata."""

from __future__ import annotations

from typing import Any

from research_mcp.adapters import ToolSpec


def build_pfc_tools(adapter: Any) -> list[ToolSpec]:
    return [
ToolSpec(
            name="pfc_run_script",
            description="Run a PFC/FISH script through the configured PFC command.",
            input_schema={
                "type": "object",
                "properties": {
                    "script_file": {
                        "type": "string",
                        "description": "Path to PFC/FISH script",
                        "minLength": 1,
                    },
                    "working_dir": {"type": "string", "description": "Working directory"},
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
                "required": ["script_file"],
            },
            handler=adapter.pfc_run_script,
        ),
        ToolSpec(
            name="pfc_parse_history",
            description="Parse PFC/DEM history output and summarize each series.",
            input_schema={
                "type": "object",
                "properties": {
                    "history_file": {
                        "type": "string",
                        "description": "CSV or whitespace history file",
                        "minLength": 1,
                    },
                    "output_plot": {
                        "type": "string",
                        "description": "Optional SVG/PNG/PDF plot path",
                    },
                },
                "required": ["history_file"],
            },
            handler=adapter.pfc_parse_history,
        ),
        ToolSpec(
            name="pfc_bridge_status",
            description="Check PFC bridge connection status and config.",
            input_schema={"type": "object", "properties": {}},
            handler=adapter.pfc_bridge_status,
        ),
        ToolSpec(
            name="pfc_execute_code",
            description="Execute Python code in a running PFC process via bridge.",
            input_schema={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Python code to execute in PFC",
                        "minLength": 1,
                    },
                    "timeout_seconds": {
                        "type": "integer",
                        "description": "Timeout in seconds",
                        "default": 10,
                        "minimum": 1,
                    },
                },
                "required": ["code"],
            },
            handler=adapter.pfc_execute_code,
        ),
        ToolSpec(
            name="pfc_execute_task",
            description="Submit a Python script for asynchronous execution in PFC via bridge.",
            input_schema={
                "type": "object",
                "properties": {
                    "entry_script": {
                        "type": "string",
                        "description": "Path to Python script executed inside PFC",
                        "minLength": 1,
                    },
                    "description": {
                        "type": "string",
                        "description": "Short task description",
                        "minLength": 1,
                    },
                },
                "required": ["entry_script", "description"],
            },
            handler=adapter.pfc_execute_task,
        ),
        ToolSpec(
            name="pfc_check_task_status",
            description="Check status and paginated output for a PFC bridge task.",
            input_schema={
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "Bridge task id",
                        "minLength": 1,
                    },
                    "skip_newest": {
                        "type": "integer",
                        "description": "Newest output lines to skip",
                        "default": 0,
                        "minimum": 0,
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum output lines",
                        "default": 64,
                        "minimum": 1,
                    },
                    "filter_text": {
                        "type": "string",
                        "description": "Optional output line filter",
                    },
                    "wait_seconds": {
                        "type": "number",
                        "description": "Optional wait for task update before rechecking",
                        "default": 1,
                    },
                },
                "required": ["task_id"],
            },
            handler=adapter.pfc_check_task_status,
        ),
        ToolSpec(
            name="pfc_list_tasks",
            description="List tracked PFC bridge tasks with pagination.",
            input_schema={
                "type": "object",
                "properties": {
                    "skip_newest": {
                        "type": "integer",
                        "description": "Newest tasks to skip",
                        "default": 0,
                        "minimum": 0,
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum tasks to return",
                        "default": 32,
                        "minimum": 1,
                    },
                },
            },
            handler=adapter.pfc_list_tasks,
        ),
        ToolSpec(
            name="pfc_interrupt_task",
            description="Request graceful interruption of a running PFC bridge task.",
            input_schema={
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "Bridge task id",
                        "minLength": 1,
                    },
                },
                "required": ["task_id"],
            },
            handler=adapter.pfc_interrupt_task,
        ),
    ]
