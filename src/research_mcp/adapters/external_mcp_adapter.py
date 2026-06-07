"""Internal capability catalog adapter.

The tool names keep the previous external_mcp_* prefix for migration
compatibility, but all returned plans point to tools served by this project.
"""

from __future__ import annotations

from typing import Any

from research_mcp.adapters import AdapterMeta, BaseAdapter, ToolSpec, register_adapter
from research_mcp.external_catalog import get_external_mcp, list_external_mcps


@register_adapter
class ExternalMCPAdapter(BaseAdapter):
    """Expose local capability replacements for formerly external MCPs."""

    adapter_name = "external_mcp_catalog"

    def metadata(self) -> AdapterMeta:
        return AdapterMeta(
            name="external_mcp_catalog",
            description="Migration catalog from external MCPs to local research-mcp tools",
            tools=[
                ToolSpec(
                    name="external_mcp_list",
                    description="List local capabilities, optionally filtered by domain.",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "domain": {"type": "string", "description": "Optional domain filter"},
                        },
                    },
                    handler=self.list_servers,
                ),
                ToolSpec(
                    name="external_mcp_get",
                    description="Get the local replacement for a former external MCP key.",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "key": {
                                "type": "string",
                                "description": "Capability or former external MCP key",
                                "minLength": 1,
                            },
                        },
                        "required": ["key"],
                    },
                    handler=self.get_server,
                ),
                ToolSpec(
                    name="external_mcp_config_snippet",
                    description="Generate the single research-mcp config snippet.",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "key": {
                                "type": "string",
                                "description": "Capability key to highlight",
                                "minLength": 1,
                            },
                            "manager": {"type": "string", "enum": ["python"], "default": "python"},
                        },
                        "required": ["key"],
                    },
                    handler=self.config_snippet,
                ),
                ToolSpec(
                    name="engineering_workflow_template",
                    description="Return a single-MCP engineering workflow template.",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "topic": {
                                "type": "string",
                                "description": "Research topic, e.g. laser waterjet rock breaking",
                            },
                            "solver": {
                                "type": "string",
                                "enum": ["comsol", "fluent", "pfc", "mixed"],
                                "default": "mixed",
                            },
                            "output": {
                                "type": "string",
                                "enum": ["paper", "report", "proposal"],
                                "default": "paper",
                            },
                        },
                    },
                    handler=self.workflow_template,
                ),
                ToolSpec(
                    name="external_mcp_compose_plan",
                    description="Generate a single-MCP composition plan.",
                    input_schema={"type": "object", "properties": {}},
                    handler=self.compose_plan,
                ),
            ],
        )

    async def initialize(self, config: dict[str, Any] | None = None) -> None:
        pass

    async def list_servers(self, domain: str = "") -> dict[str, Any]:
        entries = list_external_mcps(domain)
        return {
            "count": len(entries),
            "mode": "self_contained_research_mcp",
            "capabilities": entries,
        }

    async def get_server(self, key: str) -> dict[str, Any]:
        entry = get_external_mcp(key)
        if entry is None:
            return {"error": f"Unknown capability or former external MCP key: {key}"}
        return entry

    async def config_snippet(self, key: str, manager: str = "python") -> dict[str, Any]:
        entry = get_external_mcp(key)
        if entry is None:
            return {"error": f"Unknown capability or former external MCP key: {key}"}
        snippet = {
            "mcpServers": {
                "engineering-research-mcp": {
                    "command": "research-mcp",
                    "type": "stdio",
                    "env": {
                        "COMSOL_CMD": "comsol",
                        "FLUENT_CMD": "fluent",
                        "PFC_CMD": "pfc",
                        "LATEX_CMD": "latexmk",
                        "ZOTERO_API_KEY": "your-zotero-key",
                        "ZOTERO_LIBRARY_ID": "your-library-id",
                        "ZOTERO_LIBRARY_TYPE": "user",
                    },
                }
            }
        }
        return {
            "key": key,
            "mode": "single_mcp_config",
            "replaces": entry["replaces"],
            "internal_tools": entry["internal_tools"],
            "warning": "Use research-mcp's local tools; do not configure another MCP server.",
            "snippet": snippet,
        }

    async def workflow_template(
        self,
        topic: str = "engineering simulation research",
        solver: str = "mixed",
        output: str = "paper",
    ) -> dict[str, Any]:
        solver_stack = {
            "comsol": [
                "simulation_workflow_template",
                "simulation_check_config",
                "comsol_run_batch",
            ],
            "fluent": [
                "simulation_workflow_template",
                "simulation_check_config",
                "fluent_run_journal",
            ],
            "pfc": ["simulation_workflow_template", "simulation_check_config", "pfc_run_script"],
            "mixed": [
                "simulation_workflow_template",
                "comsol_run_batch",
                "fluent_run_journal",
                "pfc_run_script",
            ],
        }.get(solver, ["simulation_workflow_template"])
        return {
            "topic": topic,
            "target_output": output,
            "principle": "Use one research-mcp server and local tools for every stage.",
            "steps": [
                {
                    "stage": "1_literature_discovery",
                    "tools": [
                        "arxiv_search",
                        "openalex_search_works",
                        "s2_search",
                        "s2_get_references",
                    ],
                    "deliverable": "screened source pool with IDs, mechanisms, methods, and gaps",
                },
                {
                    "stage": "2_zotero_ingestion",
                    "tools": [
                        "zotero_search_items",
                        "zotero_create_collection",
                        "zotero_add_by_doi",
                        "zotero_update_item_tags",
                    ],
                    "deliverable": "Zotero collection with project-specific tags",
                },
                {
                    "stage": "3_simulation_design",
                    "tools": solver_stack,
                    "deliverable": "parameter sweep plan, scripts, and expected observables",
                },
                {
                    "stage": "4_simulation_execution",
                    "tools": solver_stack,
                    "deliverable": "raw solver outputs, logs, status, and metadata",
                },
                {
                    "stage": "5_post_processing_and_figures",
                    "tools": ["plot_xy", "plot_csv_columns"],
                    "deliverable": "publication-ready SVG/PNG/PDF figures and summary tables",
                },
                {
                    "stage": "6_writing",
                    "tools": [
                        "format_bibtex",
                        "generate_citation_key",
                        "latex_compile",
                        "docx_create",
                        "docx_add_paragraph",
                    ],
                    "deliverable": f"{output} draft with claims, evidence, and citations",
                },
            ],
        }

    async def compose_plan(self) -> dict[str, Any]:
        return {
            "principle": "Run one self-contained research-mcp server with local adapters.",
            "simulation": [
                "COMSOL, Fluent, and PFC use local solver commands.",
                "simulation_workflow_template prepares local sweep checklists.",
            ],
            "literature": [
                "arXiv, OpenAlex, and Semantic Scholar use direct public APIs from local adapters.",
                "Zotero operations use the local Zotero Web API adapter.",
            ],
            "writing_and_figures": [
                "LaTeX uses local latexmk/pdflatex through latex_* tools.",
                "Word/docx uses python-docx through docx_* tools.",
                "Figures use Matplotlib through plot_xy and plot_csv_columns.",
            ],
            "migration": [
                "Remove legacy external bridge environment variables from client configs.",
                "Replace <server>__<tool> calls with internal tool names.",
            ],
        }
