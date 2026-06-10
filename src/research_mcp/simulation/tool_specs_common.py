"""Common simulation tool metadata."""

from __future__ import annotations

from typing import Any

from research_mcp.adapters import ToolSpec


def build_common_tools(adapter: Any) -> list[ToolSpec]:
    return [
        ToolSpec(
            name="simulation_check_config",
            description=(
                "Show assistant-facing preflight config for installed local COMSOL, "
                "PFC, and Fluent workflows."
            ),
            input_schema={"type": "object", "properties": {}},
            handler=adapter.check_config,
        ),
        ToolSpec(
            name="simulation_workflow_template",
            description=(
                "Create an assistant-facing checklist for driving existing local "
                "solver workflows without replacing solver validation."
            ),
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
                        "maxItems": 100,
                    },
                },
            },
            handler=adapter.workflow_template,
        ),
    ]
