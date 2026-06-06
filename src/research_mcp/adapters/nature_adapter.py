"""Nature-style manuscript workflow planning tools."""

from __future__ import annotations

from typing import Any

from research_mcp.adapters import AdapterMeta, BaseAdapter, ToolSpec, register_adapter


@register_adapter
class NatureManuscriptAdapter(BaseAdapter):
    """Plan high-impact manuscript workflows without side effects."""

    def metadata(self) -> AdapterMeta:
        return AdapterMeta(
            name="nature_manuscript_workflows",
            description=(
                "Side-effect-free Nature-style manuscript, figure, and submission planning"
            ),
            tools=[
                ToolSpec(
                    name="nature_manuscript_plan",
                    description=(
                        "Plan a Nature-style manuscript workflow from claims, evidence, "
                        "figures, and target article type."
                    ),
                    input_schema={
                        "type": "object",
                        "properties": {
                            "title": {"type": "string", "description": "Working manuscript title"},
                            "central_claim": {
                                "type": "string",
                                "description": "Main advance or thesis of the paper",
                            },
                            "article_type": {
                                "type": "string",
                                "enum": ["article", "letter", "brief_communication", "review"],
                                "default": "article",
                            },
                            "target_journal": {
                                "type": "string",
                                "description": "Target journal or journal family",
                                "default": "Nature-family journal",
                            },
                            "claims": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Major result claims to substantiate",
                            },
                            "figures": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Planned figures or figure concepts",
                            },
                        },
                        "required": ["title", "central_claim"],
                    },
                    handler=self.manuscript_plan,
                ),
                ToolSpec(
                    name="nature_figure_package_plan",
                    description=(
                        "Plan a Nature-style multi-panel figure package linked to claims, "
                        "source data, and manuscript sections."
                    ),
                    input_schema={
                        "type": "object",
                        "properties": {
                            "storyline": {
                                "type": "string",
                                "description": "Figure narrative arc or result sequence",
                            },
                            "claims": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Claims that figures must support",
                            },
                            "data_sources": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Raw or processed data sources behind figures",
                            },
                            "preferred_format": {
                                "type": "string",
                                "enum": ["svg", "pdf", "png", "mixed"],
                                "default": "svg",
                            },
                        },
                        "required": ["storyline"],
                    },
                    handler=self.figure_package_plan,
                ),
                ToolSpec(
                    name="nature_submission_readiness_checklist",
                    description=(
                        "Create a Nature-style submission readiness checklist for evidence, "
                        "reporting, figures, data, code, and manuscript assets."
                    ),
                    input_schema={
                        "type": "object",
                        "properties": {
                            "title": {"type": "string", "description": "Working manuscript title"},
                            "has_human_or_animal_data": {"type": "boolean", "default": False},
                            "has_code_outputs": {"type": "boolean", "default": True},
                            "has_simulation_outputs": {"type": "boolean", "default": True},
                            "output_format": {
                                "type": "string",
                                "enum": ["latex", "docx", "both"],
                                "default": "latex",
                            },
                        },
                        "required": ["title"],
                    },
                    handler=self.submission_readiness_checklist,
                ),
            ],
        )

    async def initialize(self, config: dict[str, Any] | None = None) -> None:
        pass

    async def manuscript_plan(
        self,
        title: str,
        central_claim: str,
        article_type: str = "article",
        target_journal: str = "Nature-family journal",
        claims: list[str] | None = None,
        figures: list[str] | None = None,
    ) -> dict[str, Any]:
        result_claims = claims or [central_claim]
        planned_figures = figures or ["conceptual overview", "primary evidence", "validation"]
        return {
            "workflow": "nature_manuscript_plan",
            "title": title,
            "central_claim": central_claim,
            "article_type": article_type,
            "target_journal": target_journal,
            "claims": result_claims,
            "figures": planned_figures,
            "stages": [
                {
                    "stage": "editorial_positioning",
                    "tools": [
                        "research_literature_review_plan",
                        "research_capability_list",
                        "s2_get_citations",
                        "openalex_search_works",
                    ],
                    "deliverable": "one-sentence advance, audience fit, and competing-claims map",
                },
                {
                    "stage": "evidence_architecture",
                    "tools": [
                        "zotero_get_item",
                        "format_bibtex",
                        "plot_csv_columns",
                        "research_paper_asset_pack",
                    ],
                    "deliverable": "claim-to-evidence matrix with citation and figure dependencies",
                },
                {
                    "stage": "results_narrative",
                    "tools": ["nature_figure_package_plan", "generate_citation_key"],
                    "deliverable": (
                        "ordered result blocks where each figure answers one explicit question"
                    ),
                },
                {
                    "stage": "manuscript_assets",
                    "tools": [
                        "research_paper_asset_pack",
                        "latex_validate_project",
                        "docx_read",
                    ],
                    "deliverable": (
                        "abstract, display-item map, references, and manuscript "
                        "validation plan"
                    ),
                },
                {
                    "stage": "submission_readiness",
                    "tools": ["nature_submission_readiness_checklist"],
                    "deliverable": "gap list for reporting, data, code, figures, and editorial fit",
                },
            ],
            "quality_bar": [
                "state the advance before describing methods",
                "tie every primary claim to at least one display item and one source artifact",
                "separate demonstrated evidence from interpretation and speculation",
                "preserve source data and analysis commands for every quantitative figure",
            ],
            "required_services": [
                "public literature APIs for positioning",
                "Zotero credentials for evidence retrieval if using library records",
                "LaTeX or docx tooling for manuscript asset validation",
            ],
        }

    async def figure_package_plan(
        self,
        storyline: str,
        claims: list[str] | None = None,
        data_sources: list[str] | None = None,
        preferred_format: str = "svg",
    ) -> dict[str, Any]:
        figure_claims = claims or []
        sources = data_sources or []
        return {
            "workflow": "nature_figure_package_plan",
            "storyline": storyline,
            "claims": figure_claims,
            "data_sources": sources,
            "preferred_format": preferred_format,
            "stages": [
                {
                    "stage": "display_item_strategy",
                    "tools": ["research_paper_asset_pack"],
                    "deliverable": "main-text versus extended-data figure allocation",
                },
                {
                    "stage": "panel_design",
                    "tools": ["plot_xy", "plot_csv_columns"],
                    "deliverable": (
                        "panel list with visual encoding, source data, and statistical "
                        "notes"
                    ),
                },
                {
                    "stage": "source_data_traceability",
                    "tools": ["plot_csv_columns", "format_bibtex"],
                    "deliverable": "source-data ledger linking each panel to raw files and methods",
                },
                {
                    "stage": "figure_quality_control",
                    "tools": ["nature_submission_readiness_checklist"],
                    "deliverable": (
                        "readability, file-format, labeling, and evidence-integrity "
                        "checklist"
                    ),
                },
            ],
            "panel_principles": [
                "one message per panel",
                "show controls before mechanisms when the causal claim depends on them",
                "avoid decorative panels that do not support a manuscript claim",
                "keep quantitative panels reproducible from stored source data",
            ],
            "output_expectations": [
                f"primary editable format: {preferred_format}",
                "source data retained beside final display items",
                "caption claims match plotted evidence",
            ],
        }

    async def submission_readiness_checklist(
        self,
        title: str,
        has_human_or_animal_data: bool = False,
        has_code_outputs: bool = True,
        has_simulation_outputs: bool = True,
        output_format: str = "latex",
    ) -> dict[str, Any]:
        supported_formats = {"latex", "docx", "both"}
        if output_format not in supported_formats:
            raise ValueError(f"Unsupported output_format: {output_format}")

        manuscript_tools = ["latex_validate_project"] if output_format == "latex" else ["docx_read"]
        if output_format == "both":
            manuscript_tools = ["latex_validate_project", "docx_read"]
        reporting_checks = [
            "scope and novelty are explicit in title, abstract, and opening paragraph",
            "every central claim has a source artifact, figure, and citation trail",
            "limitations are distinguished from unsupported speculation",
            "references are deduplicated and formatted consistently",
        ]
        if has_human_or_animal_data:
            reporting_checks.append("ethics approvals and reporting checklists are accounted for")
        if has_code_outputs:
            reporting_checks.append(
                "code availability and computational environment are documented"
            )
        if has_simulation_outputs:
            reporting_checks.append(
                "solver versions, licenses, parameters, and raw outputs are recorded"
            )
        return {
            "workflow": "nature_submission_readiness_checklist",
            "title": title,
            "output_format": output_format,
            "stages": [
                {
                    "stage": "manuscript_validation",
                    "tools": manuscript_tools,
                    "deliverable": "compile/read validation result and missing asset list",
                },
                {
                    "stage": "reference_validation",
                    "tools": ["parse_bibtex", "format_bibtex", "zotero_search_items"],
                    "deliverable": "deduplicated references with stable citation keys",
                },
                {
                    "stage": "data_and_code_availability",
                    "tools": ["research_capability_list", "plot_csv_columns"],
                    "deliverable": "data, code, solver-output, and figure-source availability map",
                },
                {
                    "stage": "editorial_risk_review",
                    "tools": ["research_literature_review_plan"],
                    "deliverable": (
                        "overclaiming, novelty, reproducibility, and missing-control "
                        "risk list"
                    ),
                },
            ],
            "checks": reporting_checks,
            "required_services": [
                "manuscript source files",
                "BibTeX or Zotero records",
                "source data for all quantitative figures",
            ],
        }
