"""Workflow-level research planning tools."""

from __future__ import annotations

from typing import Any

from research_mcp.adapters import AdapterMeta, BaseAdapter, ToolSpec, register_adapter
from research_mcp.external_catalog import get_capability, list_capabilities


@register_adapter
class WorkflowAdapter(BaseAdapter):
    """Compose existing local tools into reusable research workflows."""

    def metadata(self) -> AdapterMeta:
        return AdapterMeta(
            name="research_workflows",
            description=(
                "Side-effect-free research workflow plans built from local research-mcp tools"
            ),
            tools=[
                ToolSpec(
                    name="research_capability_list",
                    description=(
                        "List local research-mcp capabilities with maturity and workflow metadata."
                    ),
                    input_schema={
                        "type": "object",
                        "properties": {
                            "domain": {
                                "type": "string",
                                "description": "Optional domain/key filter",
                            },
                            "maturity": {
                                "type": "string",
                                "enum": ["", "stable", "experimental", "migration"],
                                "default": "",
                            },
                            "workflow_role": {
                                "type": "string",
                                "description": "Optional workflow role filter",
                            },
                        },
                    },
                    handler=self.capability_list,
                ),
                ToolSpec(
                    name="research_capability_get",
                    description=(
                        "Get one local research-mcp capability by key or replaced MCP name."
                    ),
                    input_schema={
                        "type": "object",
                        "properties": {
                            "key": {
                                "type": "string",
                                "description": "Capability key or replaced MCP name",
                            },
                        },
                        "required": ["key"],
                    },
                    handler=self.capability_get,
                ),
                ToolSpec(
                    name="research_literature_review_plan",
                    description=(
                        "Plan a literature-review workflow using search, citation, and "
                        "Zotero tools."
                    ),
                    input_schema={
                        "type": "object",
                        "properties": {
                            "topic": {"type": "string", "description": "Research topic"},
                            "time_range": {"type": "string", "description": "Optional time range"},
                            "target_venues": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Optional target venues or communities",
                            },
                        },
                        "required": ["topic"],
                    },
                    handler=self.literature_review_plan,
                ),
                ToolSpec(
                    name="research_simulation_study_plan",
                    description=(
                        "Plan a simulation study using COMSOL, Fluent, PFC, parser, and figure "
                        "tools."
                    ),
                    input_schema={
                        "type": "object",
                        "properties": {
                            "research_question": {
                                "type": "string",
                                "description": "Study question",
                            },
                            "solver": {
                                "type": "string",
                                "enum": ["comsol", "fluent", "pfc", "mixed"],
                                "default": "mixed",
                            },
                            "parameters": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Control variables or sweep parameters",
                            },
                            "observables": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Expected outputs or measured quantities",
                            },
                        },
                        "required": ["research_question"],
                    },
                    handler=self.simulation_study_plan,
                ),
                ToolSpec(
                    name="research_paper_asset_pack",
                    description=(
                        "Plan manuscript assets from claims, figures, references, and "
                        "output format."
                    ),
                    input_schema={
                        "type": "object",
                        "properties": {
                            "title": {"type": "string", "description": "Working paper title"},
                            "claims": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Core paper claims",
                            },
                            "output_format": {
                                "type": "string",
                                "enum": ["latex", "docx", "both"],
                                "default": "latex",
                            },
                        },
                        "required": ["title"],
                    },
                    handler=self.paper_asset_pack,
                ),
            ],
        )

    async def initialize(self, config: dict[str, Any] | None = None) -> None:
        pass

    async def capability_list(
        self,
        domain: str = "",
        maturity: str = "",
        workflow_role: str = "",
    ) -> dict[str, Any]:
        capabilities = list_capabilities(
            domain=domain,
            maturity=maturity,
            workflow_role=workflow_role,
        )
        return {
            "count": len(capabilities),
            "filters": {
                "domain": domain,
                "maturity": maturity,
                "workflow_role": workflow_role,
            },
            "capabilities": capabilities,
        }

    async def capability_get(self, key: str) -> dict[str, Any]:
        capability = get_capability(key)
        if capability is None:
            return {"error": f"Unknown capability: {key}"}
        return capability

    async def literature_review_plan(
        self,
        topic: str,
        time_range: str = "",
        target_venues: list[str] | None = None,
    ) -> dict[str, Any]:
        venues = target_venues or []
        return {
            "topic": topic,
            "time_range": time_range,
            "target_venues": venues,
            "workflow": "literature_review",
            "stages": [
                {
                    "stage": "query_design",
                    "tools": ["arxiv_search", "s2_search", "openalex_search_works"],
                    "deliverable": "search strings, inclusion criteria, and initial paper pool",
                },
                {
                    "stage": "citation_expansion",
                    "tools": ["s2_get_references", "s2_get_citations", "openalex_get_work"],
                    "deliverable": "backward/forward citation map and influential works",
                },
                {
                    "stage": "library_management",
                    "tools": [
                        "zotero_search_items",
                        "zotero_add_by_doi",
                        "zotero_update_item_tags",
                    ],
                    "deliverable": "deduplicated Zotero collection with project tags",
                },
                {
                    "stage": "synthesis_assets",
                    "tools": ["generate_citation_key", "format_bibtex", "parse_bibtex"],
                    "deliverable": "citation keys, BibTeX records, gap map, and reusable notes",
                },
            ],
            "required_services": ["public paper APIs", "Zotero credentials for library writes"],
            "reproducibility_checks": [
                "record exact queries and dates",
                "save screened inclusion/exclusion decisions",
                "preserve DOI/arXiv/OpenAlex/Semantic Scholar identifiers",
            ],
        }

    async def simulation_study_plan(
        self,
        research_question: str,
        solver: str = "mixed",
        parameters: list[str] | None = None,
        observables: list[str] | None = None,
    ) -> dict[str, Any]:
        solver_tools = {
            "comsol": [
                "comsol_check_mph",
                "comsol_server_connect",
                "comsol_solve",
                "comsol_parse_table",
            ],
            "fluent": ["fluent_check_pyfluent", "fluent_launch_session", "fluent_parse_residuals"],
            "pfc": ["pfc_bridge_status", "pfc_execute_task", "pfc_parse_history"],
            "mixed": ["comsol_parse_table", "fluent_parse_residuals", "pfc_parse_history"],
        }.get(solver, ["simulation_workflow_template"])
        return {
            "research_question": research_question,
            "solver": solver,
            "parameters": parameters or [],
            "observables": observables or [],
            "workflow": "simulation_study",
            "stages": [
                {
                    "stage": "study_design",
                    "tools": ["simulation_workflow_template", "simulation_check_config"],
                    "deliverable": "parameter matrix, solver requirements, and run checklist",
                },
                {
                    "stage": "execution",
                    "tools": solver_tools,
                    "deliverable": "solver outputs, logs, status records, and raw tables",
                },
                {
                    "stage": "post_processing",
                    "tools": ["comsol_parse_table", "fluent_parse_residuals", "pfc_parse_history"],
                    "deliverable": (
                        "summary statistics, convergence diagnostics, and parsed histories"
                    ),
                },
                {
                    "stage": "figure_generation",
                    "tools": ["plot_xy", "plot_csv_columns"],
                    "deliverable": "publication-friendly SVG/PNG/PDF figures",
                },
            ],
            "required_services": ["local solver installation and license for live execution"],
            "reproducibility_checks": [
                "record solver version and command paths",
                "store parameter table and resolved config",
                "retain raw outputs before plotting",
                "separate stable parsers from experimental live solver controls",
            ],
        }

    async def paper_asset_pack(
        self,
        title: str,
        claims: list[str] | None = None,
        output_format: str = "latex",
    ) -> dict[str, Any]:
        formats = ["latex", "docx"] if output_format == "both" else [output_format]
        writing_tools = ["generate_citation_key", "format_bibtex", "parse_bibtex"]
        submission_tools: list[str] = []
        required_services: list[str] = []
        if "latex" in formats:
            writing_tools.extend(["latex_validate_project", "latex_compile"])
            submission_tools.append("latex_validate_project")
            required_services.append("LaTeX toolchain for PDF builds")
        if "docx" in formats:
            writing_tools.extend(["docx_create", "docx_add_heading", "docx_add_paragraph"])
            submission_tools.append("docx_read")
            required_services.append("python-docx")
        return {
            "title": title,
            "claims": claims or [],
            "output_format": output_format,
            "workflow": "paper_asset_pack",
            "stages": [
                {
                    "stage": "evidence_map",
                    "tools": ["zotero_get_item", "format_bibtex", "plot_csv_columns"],
                    "deliverable": "claim-to-evidence table with figures and references",
                },
                {
                    "stage": "manuscript_assets",
                    "tools": writing_tools,
                    "deliverable": "validated manuscript skeleton and citation assets",
                },
                {
                    "stage": "submission_readiness",
                    "tools": submission_tools,
                    "deliverable": "missing-assets checklist and compile/read validation results",
                },
            ],
            "required_services": required_services,
            "reproducibility_checks": [
                "keep source data behind every figure",
                "store BibTeX beside manuscript source",
                "record compile command and warnings",
            ],
        }
