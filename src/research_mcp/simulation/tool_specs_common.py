"""Common simulation tool metadata."""

from __future__ import annotations

from typing import Any

from research_mcp.adapters import ToolSpec


def build_common_tools(adapter: Any) -> list[ToolSpec]:
    return [
        ToolSpec(
            name="simulation_check_config",
            description="Show configured command names/paths for COMSOL, PFC, and Fluent.",
            input_schema={"type": "object", "properties": {}},
            handler=adapter.check_config,
        ),
        ToolSpec(
            name="simulation_workflow_template",
            description="Create a local simulation workflow checklist.",
            input_schema={
                "type": "object",
                "properties": {
                    "solver": {
                        "type": "string",
                        "enum": ["comsol", "fluent", "pfc", "mixed"],
                        "default": "mixed",
                    },
                    "objective": {"type": "string", "description": "Simulation objective"},
                    "parameters": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Parameter names to sweep",
                    },
                },
            },
            handler=adapter.workflow_template,
        ),
    ]
