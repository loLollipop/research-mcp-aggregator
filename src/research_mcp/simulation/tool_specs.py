"""Tool metadata for the simulation adapter."""

from __future__ import annotations

from typing import Any

from research_mcp.adapters import ToolSpec
from research_mcp.simulation.tool_specs_common import build_common_tools
from research_mcp.simulation.tool_specs_comsol import build_comsol_tools
from research_mcp.simulation.tool_specs_fluent import build_fluent_tools
from research_mcp.simulation.tool_specs_pfc import build_pfc_tools


def build_simulation_tools(adapter: Any) -> list[ToolSpec]:
    return [
        *build_common_tools(adapter),
        *build_comsol_tools(adapter),
        *build_fluent_tools(adapter),
        *build_pfc_tools(adapter),
    ]
