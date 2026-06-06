"""Internal capability catalog for the self-contained research MCP.

The public tool names keep the old external_mcp_* prefix for migration
compatibility, but entries now describe capabilities served by this project.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class InternalCapability:
    """Description of a formerly external capability now served locally."""

    key: str
    domain: str
    name: str
    status: str
    purpose: str
    internal_tools: tuple[str, ...]
    replaces: tuple[str, ...]
    configuration: str
    notes: str = ""
    maturity: str = "stable"
    dependencies: tuple[str, ...] = ()
    workflow_roles: tuple[str, ...] = ()
    output_types: tuple[str, ...] = ()


INTERNAL_CAPABILITIES: tuple[InternalCapability, ...] = (
    InternalCapability(
        key="comsol",
        domain="simulation/comsol",
        name="COMSOL MPh and batch workflows",
        status="local adapter with upstream-derived MPh backend and batch fallback",
        purpose=(
            "Live COMSOL Server connection, model/parameter/solve lifecycle "
            "ported from comsol-mcp (MIT) semantics, plus batch command and "
            "table parsing fallback."
        ),
        internal_tools=(
            "simulation_check_config",
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
            "simulation_workflow_template",
        ),
        replaces=("comsol-multiphysics-mcp", "comsol-mcp"),
        configuration=(
            "Install the comsol extra for MPh live control; set COMSOL_CMD for "
            "command-line batch fallback."
        ),
        maturity="experimental",
        dependencies=("MPh", "JPype1", "COMSOL Multiphysics Server", "COMSOL_CMD"),
        workflow_roles=("simulation_design", "simulation_execution", "post_processing"),
        output_types=("model_metadata", "parameter_table", "solve_status", "result_table"),
    ),
    InternalCapability(
        key="fluent",
        domain="simulation/fluent",
        name="ANSYS Fluent PyFluent and batch workflows",
        status="local adapter with upstream-derived PyFluent backend and journal fallback",
        purpose=(
            "PyFluent session control ported from ansys-mcp-server semantics, "
            "plus fallback journal execution and residual post-processing."
        ),
        internal_tools=(
            "simulation_check_config",
            "fluent_check_pyfluent",
            "fluent_launch_session",
            "fluent_inspect_file",
            "fluent_list_sessions",
            "fluent_execute_tui",
            "fluent_close_session",
            "fluent_run_journal",
            "fluent_parse_residuals",
            "simulation_workflow_template",
        ),
        replaces=("ansys-mcp-server",),
        configuration=(
            "Install the fluent extra for PyFluent control; set FLUENT_CMD for "
            "command-line journal fallback."
        ),
        maturity="experimental",
        dependencies=("ansys-fluent-core", "local Ansys licensing", "FLUENT_CMD"),
        workflow_roles=("simulation_design", "simulation_execution", "post_processing"),
        output_types=("session_metadata", "journal_log", "residual_history", "convergence_plot"),
    ),
    InternalCapability(
        key="pfc",
        domain="simulation/pfc",
        name="Itasca PFC script workflows",
        status="local adapter with vendored pfc-mcp docs and bridge backend",
        purpose=(
            "PFC documentation tools and bridge execution ported from pfc-mcp, "
            "plus fallback script/history workflows."
        ),
        internal_tools=(
            "pfc_docs_status",
            "pfc_browse_commands",
            "pfc_query_command",
            "pfc_browse_python_api",
            "pfc_query_python_api",
            "pfc_bridge_status",
            "pfc_execute_code",
            "pfc_execute_task",
            "pfc_check_task_status",
            "pfc_list_tasks",
            "pfc_interrupt_task",
            "simulation_check_config",
            "pfc_run_script",
            "pfc_parse_history",
            "simulation_workflow_template",
        ),
        replaces=("pfc-mcp",),
        configuration="Set PFC_CMD to the local PFC executable if it is not on PATH.",
        maturity="experimental",
        dependencies=("websockets", "PFC", "itasca-mcp-bridge", "PFC_CMD"),
        workflow_roles=("simulation_design", "simulation_execution", "documentation_lookup"),
        output_types=("command_docs", "python_api_docs", "history_table", "bridge_task_status"),
    ),
    InternalCapability(
        key="zotero",
        domain="literature/zotero",
        name="Zotero Web API workflows",
        status="local adapter",
        purpose="Search, inspect, update, and import Zotero library items.",
        internal_tools=(
            "zotero_status",
            "zotero_search_items",
            "zotero_get_item",
            "zotero_create_collection",
            "zotero_add_by_doi",
            "zotero_update_item_tags",
        ),
        replaces=("mcp-zotero",),
        configuration="Set ZOTERO_API_KEY, ZOTERO_LIBRARY_ID, and ZOTERO_LIBRARY_TYPE.",
        maturity="stable",
        dependencies=("Zotero Web API credentials",),
        workflow_roles=("reference_management", "literature_ingestion"),
        output_types=("zotero_item", "collection", "tag_update"),
    ),
    InternalCapability(
        key="arxiv",
        domain="literature/arxiv",
        name="arXiv search",
        status="local adapter",
        purpose="Search and fetch arXiv paper metadata through the public arXiv API.",
        internal_tools=("arxiv_search", "arxiv_get_paper"),
        replaces=("arxiv-mcp-server",),
        configuration="No MCP server configuration is required.",
        maturity="stable",
        dependencies=("public arXiv API",),
        workflow_roles=("literature_discovery", "source_pooling"),
        output_types=("paper_metadata", "preprint_record"),
    ),
    InternalCapability(
        key="openalex",
        domain="literature/openalex",
        name="OpenAlex scholarly graph",
        status="local adapter",
        purpose="Search works and inspect works/authors through OpenAlex.",
        internal_tools=(
            "openalex_search_works",
            "openalex_get_work",
            "openalex_get_author",
        ),
        replaces=("openalex-mcp-server", "alex-mcp"),
        configuration="Optionally provide an OpenAlex mailto email in adapter config.",
        maturity="stable",
        dependencies=("public OpenAlex API",),
        workflow_roles=("literature_discovery", "bibliometric_context"),
        output_types=("work_metadata", "author_metadata", "scholarly_graph_record"),
    ),
    InternalCapability(
        key="semantic-scholar",
        domain="literature/semantic-scholar",
        name="Semantic Scholar citation graph",
        status="local adapter",
        purpose="Search papers and inspect Semantic Scholar citation neighborhoods.",
        internal_tools=(
            "s2_search",
            "s2_get_paper",
            "s2_get_citations",
            "s2_get_references",
        ),
        replaces=("semanticscholar-mcp-server",),
        configuration="Optionally provide a Semantic Scholar API key in adapter config.",
        maturity="stable",
        dependencies=("Semantic Scholar API",),
        workflow_roles=("literature_discovery", "citation_mapping"),
        output_types=("paper_metadata", "citation_list", "reference_list"),
    ),
    InternalCapability(
        key="latex",
        domain="writing/latex",
        name="LaTeX manuscript workflows",
        status="local adapter",
        purpose="Validate and compile local LaTeX projects through latexmk or pdflatex.",
        internal_tools=(
            "latex_check_config",
            "latex_validate_project",
            "latex_compile",
            "latex_create_minimal_project",
        ),
        replaces=("mcp-latex-server",),
        configuration="Set LATEX_CMD, defaulting to latexmk.",
        maturity="stable",
        dependencies=("latexmk or pdflatex",),
        workflow_roles=("manuscript_preparation", "artifact_validation"),
        output_types=("latex_project", "compile_log", "pdf_artifact"),
    ),
    InternalCapability(
        key="docx",
        domain="writing/docx",
        name="Word/docx document workflows",
        status="local adapter",
        purpose="Create, read, and append basic content to Word .docx files through python-docx.",
        internal_tools=(
            "docx_create",
            "docx_read",
            "docx_add_heading",
            "docx_add_paragraph",
            "docx_add_table",
        ),
        replaces=("office-word-mcp-server", "docx-mcp"),
        configuration="Install project dependencies; no Word MCP server is needed.",
        maturity="stable",
        dependencies=("python-docx",),
        workflow_roles=("report_preparation", "artifact_inspection"),
        output_types=("docx_document", "document_outline", "table"),
    ),
    InternalCapability(
        key="visualization",
        domain="figures/visualization",
        name="Scientific figure generation",
        status="local adapter",
        purpose="Generate SVG/PNG/PDF plots from arrays or CSV data through Matplotlib.",
        internal_tools=("plot_xy", "plot_csv_columns"),
        replaces=("visualization-mcp-server",),
        configuration="Matplotlib is included in the base project dependencies.",
        maturity="stable",
        dependencies=("matplotlib",),
        workflow_roles=("post_processing", "figure_generation"),
        output_types=("svg_figure", "png_figure", "pdf_figure"),
    ),
    InternalCapability(
        key="nature-manuscript",
        domain="writing/nature",
        name="Nature-style manuscript workflow planning",
        status="local side-effect-free workflow adapter",
        purpose=(
            "Plan Nature-style manuscript narratives, figure packages, and "
            "submission-readiness checks from claims, evidence, and source assets."
        ),
        internal_tools=(
            "nature_manuscript_plan",
            "nature_figure_package_plan",
            "nature_submission_readiness_checklist",
        ),
        replaces=("nature-writing-skills", "nature-figure-skills"),
        configuration="No external service configuration is required for planning tools.",
        maturity="stable",
        dependencies=("manuscript source assets", "figure source data", "citation records"),
        workflow_roles=(
            "manuscript_preparation",
            "figure_generation",
            "submission_readiness",
        ),
        output_types=("manuscript_plan", "figure_package_plan", "submission_checklist"),
    ),
)


def _as_dict(entry: InternalCapability) -> dict[str, object]:
    return {
        "key": entry.key,
        "domain": entry.domain,
        "name": entry.name,
        "status": entry.status,
        "purpose": entry.purpose,
        "internal_tools": list(entry.internal_tools),
        "replaces": list(entry.replaces),
        "configuration": entry.configuration,
        "notes": entry.notes,
        "maturity": entry.maturity,
        "dependencies": list(entry.dependencies),
        "workflow_roles": list(entry.workflow_roles),
        "output_types": list(entry.output_types),
    }


def list_capabilities(
    domain: str = "",
    maturity: str = "",
    workflow_role: str = "",
) -> list[dict[str, object]]:
    """Return local capabilities, optionally filtered by domain, maturity, or role."""
    entries = INTERNAL_CAPABILITIES
    if domain:
        needle = domain.lower()
        entries = tuple(
            entry
            for entry in entries
            if needle in entry.domain.lower()
            or needle in entry.key.lower()
            or any(needle in replaced.lower() for replaced in entry.replaces)
        )
    if maturity:
        normalized_maturity = maturity.lower()
        entries = tuple(entry for entry in entries if entry.maturity.lower() == normalized_maturity)
    if workflow_role:
        normalized_role = workflow_role.lower()
        entries = tuple(
            entry
            for entry in entries
            if any(normalized_role in role.lower() for role in entry.workflow_roles)
        )
    return [_as_dict(entry) for entry in entries]


def get_capability(key: str) -> dict[str, object] | None:
    """Return one local capability by key or replaced external MCP key."""
    normalized = key.lower()
    for entry in INTERNAL_CAPABILITIES:
        if entry.key == normalized or normalized in {item.lower() for item in entry.replaces}:
            return _as_dict(entry)
    return None


def list_external_mcps(domain: str = "") -> list[dict[str, object]]:
    """Return local replacement capabilities, optionally filtered by domain/key."""
    return list_capabilities(domain=domain)


def get_external_mcp(key: str) -> dict[str, object] | None:
    """Return one local capability by key or replaced external MCP key."""
    return get_capability(key)
