# Engineering Research MCP

> Self-contained research workflow server that unifies literature discovery, reference management, simulation control, data-to-figure pipelines, and manuscript preparation through one Model Context Protocol interface.

This project is designed as a research operating layer for engineering workflows where a researcher often needs to:

1. search papers,
2. save useful papers into Zotero,
3. run or manage COMSOL / PFC / Fluent simulations,
4. convert results into figures,
5. prepare references, LaTeX manuscripts, Word reports, and Nature-style submission assets.

## Self-contained architecture

This project exposes one MCP server: `research-mcp`. It no longer requires users to configure companion MCP servers for Zotero, arXiv, COMSOL, Fluent, PFC, LaTeX, docx, or visualization workflows.

The server uses local adapters:

- literature search calls public APIs such as arXiv, Semantic Scholar, and OpenAlex directly;
- Zotero integration uses Zotero Web API semantics;
- COMSOL uses an internal MPh backend ported from upstream comsol-mcp semantics, with batch command fallback;
- Fluent uses an internal PyFluent backend ported from upstream ANSYS MCP semantics, with command-line journal fallback;
- PFC uses vendored `pfc-mcp` documentation resources and an internal bridge backend, with script/history fallback;
- figures use Matplotlib and save publication-friendly files;
- LaTeX uses a local `latexmk` or `pdflatex` command;
- Word/docx support uses `python-docx`;
- each domain is registered into one MCP server.

The simulation layer is now being refocused around upstream source internalization:

- runtime stays as one `research-mcp` server;
- mature COMSOL / Fluent / PFC MCP repositories are vendored only for source audit;
- useful backend logic is ported into local adapters instead of proxied as external MCP tools;
- current batch/script commands and table parsers remain fallback tools while deeper upstream-derived backends are migrated.

The legacy tools named `external_mcp_*` remain as migration helpers, but they return internal replacement tools rather than configs for other MCP servers.

## Capability maturity

`research-mcp` distinguishes stable local utilities from experimental live integrations so users can compose workflows without mistaking parser coverage for solver validation.

| Maturity | Meaning | Examples |
| --- | --- | --- |
| Stable | Local tools with deterministic behavior or public API dependencies | arXiv/OpenAlex/Semantic Scholar search, Zotero metadata operations, BibTeX utilities, Matplotlib figures, LaTeX/docx helpers, exported table parsers |
| Experimental | Live engineering-software control that depends on local installation, licensing, optional Python packages, and machine-specific solver state | COMSOL MPh sessions, PyFluent sessions, live PFC bridge execution |
| Migration | Compatibility helpers that map former external MCP names to internal `research-mcp` capabilities | `external_mcp_*` catalog and compose-plan tools |

## Research workflow tools

The `research_*` tools are side-effect-free orchestration helpers. They do not search the web, write to Zotero, launch solvers, compile manuscripts, or create figures directly; they return structured plans that compose the lower-level tools listed below.

| Tool | Purpose |
| --- | --- |
| `research_capability_list` | List local capabilities with maturity, dependencies, workflow roles, and output types |
| `research_capability_get` | Inspect one capability by local key or replaced external MCP name |
| `research_literature_review_plan` | Compose paper search, citation expansion, Zotero/library management, and BibTeX synthesis stages |
| `research_simulation_study_plan` | Compose simulation design, live/batch execution, parser, and figure-generation stages |
| `research_paper_asset_pack` | Compose claim-evidence mapping, citation assets, LaTeX/docx manuscript assets, and submission checks |
| `nature_manuscript_plan` | Plan a Nature-style manuscript narrative from central claim, evidence, figures, and target journal fit |
| `nature_figure_package_plan` | Plan a multi-panel figure package with claim alignment, source-data traceability, and quality control |
| `nature_submission_readiness_checklist` | Create a submission-readiness checklist for manuscript assets, evidence, reporting, data, code, and simulation outputs |

## Current tools

| Module | Tools | Purpose |
| --- | --- | --- |
| Research workflows | `research_capability_list`, `research_capability_get`, `research_literature_review_plan`, `research_simulation_study_plan`, `research_paper_asset_pack` | Compose lower-level tools into side-effect-free literature review, simulation study, and manuscript asset plans |
| Nature manuscript workflows | `nature_manuscript_plan`, `nature_figure_package_plan`, `nature_submission_readiness_checklist` | Compose Nature-style manuscript narrative, figure package, evidence, reporting, data/code, and submission-readiness plans |
| Internal capability catalog | `external_mcp_list`, `external_mcp_get`, `external_mcp_config_snippet`, `external_mcp_compose_plan`, `engineering_workflow_template` | Map formerly external MCP needs to local `research-mcp` tools and compose migration-friendly one-server workflows |
| ArXiv | `arxiv_search`, `arxiv_get_paper` | Search preprints and fetch paper metadata |
| Semantic Scholar | `s2_search`, `s2_get_paper`, `s2_get_citations`, `s2_get_references` | Search papers and citation/reference networks |
| OpenAlex | `openalex_search_works`, `openalex_get_work`, `openalex_get_author` | Open scholarly search, work details, and author metadata |
| Zotero | `zotero_status`, `zotero_search_items`, `zotero_get_item`, `zotero_create_collection`, `zotero_add_by_doi`, `zotero_update_item_tags` | Manage literature library records and tags through Zotero Web API |
| Simulation | `simulation_check_config`, `simulation_workflow_template`, `comsol_check_mph`, `comsol_server_connect`, `comsol_server_disconnect`, `comsol_server_info`, `comsol_model_load`, `comsol_model_create`, `comsol_get_parameters`, `comsol_set_parameters`, `comsol_solve`, `comsol_solve_status`, `comsol_list_studies`, `comsol_inspect_file`, `comsol_run_batch`, `comsol_parse_table`, `fluent_check_pyfluent`, `fluent_launch_session`, `fluent_inspect_file`, `fluent_list_sessions`, `fluent_execute_tui`, `fluent_close_session`, `fluent_run_journal`, `fluent_parse_residuals`, `pfc_run_script`, `pfc_parse_history`, `pfc_bridge_status`, `pfc_execute_code`, `pfc_execute_task`, `pfc_check_task_status`, `pfc_list_tasks`, `pfc_interrupt_task` | Plan, run, post-process, and bridge-connect COMSOL, Fluent, and PFC workflows |
| PFC docs | `pfc_docs_status`, `pfc_browse_commands`, `pfc_query_command`, `pfc_browse_python_api`, `pfc_query_python_api` | Browse/search PFC command and Python API documentation ported from vendored `pfc-mcp` resources |
| Figure | `plot_xy`, `plot_csv_columns` | Create SVG/PNG/PDF figures from arrays or CSV columns |
| Writing | `format_bibtex`, `generate_citation_key`, `parse_bibtex` | Citation keys and BibTeX formatting/parsing |
| LaTeX | `latex_check_config`, `latex_validate_project`, `latex_compile`, `latex_create_minimal_project` | Validate and compile local LaTeX manuscripts |
| Word/docx | `docx_create`, `docx_read`, `docx_add_heading`, `docx_add_paragraph`, `docx_add_table` | Create, inspect, and update `.docx` reports |

## Simulation configuration

Simulation support is split into stable local planning/parsing tools and experimental live solver controls. Templates, file inspection, exported table parsing, residual parsing, history parsing, and plotting can run locally from files. Live COMSOL, Fluent, and PFC control additionally requires the corresponding commercial software, a valid local license, optional Python packages, and machine-specific environment setup.

The simulation adapter wraps command-line executables. Set these environment variables to match your installation:

```bash
export COMSOL_CMD="/path/to/comsol"
export FLUENT_CMD="/path/to/fluent"
export PFC_CMD="/path/to/pfc"
export SIM_TIMEOUT_SECONDS="3600"
```

On Windows, configure equivalent environment variables or pass full executable paths through MCP config.

Typical usage:

- `simulation_workflow_template` creates a parameter-sweep and reproducibility checklist;
- `comsol_check_mph` checks whether the MPh library is importable;
- `comsol_server_connect`, `comsol_model_load`, `comsol_model_create`, `comsol_get_parameters`, `comsol_set_parameters`, `comsol_solve`, and `comsol_list_studies` control live COMSOL Server sessions through the internal MPh backend (ported from `comsol-mcp`);
- `comsol_server_disconnect`, `comsol_server_info`, and `comsol_inspect_file` manage connections and inspect COMSOL files;
- `comsol_solve_status` polls background solve jobs started with `comsol_solve(async_mode=true)`;
- `comsol_run_batch` runs `comsol batch -inputfile model.mph ...` as a command-line fallback;
- `comsol_parse_table` summarizes COMSOL exported tables and can plot curves;
- `fluent_check_pyfluent` checks whether `ansys.fluent.core` is importable;
- `fluent_launch_session`, `fluent_execute_tui`, `fluent_list_sessions`, and `fluent_close_session` control live Fluent sessions through the internal PyFluent backend;
- `fluent_inspect_file` identifies Fluent case/data/journal files and previews journal text;
- `fluent_run_journal` runs Fluent with `-g -i journal.jou` as a command-line fallback;
- `fluent_parse_residuals` reads residual histories, checks convergence, and can plot curves;
- `pfc_run_script` runs the configured PFC command with a FISH/script file;
- `pfc_parse_history` summarizes PFC/DEM history tables and can plot time histories;
- `pfc_bridge_status` shows bridge connection config and status;
- `pfc_execute_code` runs Python code in a live PFC process via the internal bridge backend (ported from `pfc-mcp`);
- `pfc_execute_task`, `pfc_check_task_status`, `pfc_list_tasks`, and `pfc_interrupt_task` manage long-running PFC bridge tasks;
- `pfc_browse_commands`, `pfc_query_command`, `pfc_browse_python_api`, and `pfc_query_python_api` use vendored `pfc-mcp` docs locally without a runtime bridge.

For live COMSOL control, install the optional COMSOL extra and make sure a COMSOL Multiphysics Server is running:

```bash
uv pip install -e ".[comsol]"
```

The preferred workflow is attach-first: start COMSOL Multiphysics Server manually, then call `comsol_server_connect`. The command-line `comsol_run_batch` fallback only requires `COMSOL_CMD` to point to a usable COMSOL executable.

For live Fluent control, install the optional Fluent extra and make sure local Ansys licensing is configured:

```bash
uv pip install -e ".[fluent]"
```

The command-line `fluent_run_journal` fallback only requires `FLUENT_CMD` to point to a usable Fluent executable.

For live PFC bridge execution, install this project with the simulation extra so the MCP-side WebSocket client is available:

```bash
uv pip install -e ".[simulation]"
```

Then start the bridge inside the PFC GUI process using the upstream `itasca-mcp-bridge` package:

```python
import itasca_mcp_bridge

itasca_mcp_bridge.start()
```

The default bridge URL is `ws://localhost:9001`; override it with `PFC_MCP_BRIDGE_URL` if your bridge listens elsewhere.

The adapter validates input files and returns command, stdout, stderr, return code, and status.

## Zotero configuration

Set:

```bash
export ZOTERO_API_KEY="..."
export ZOTERO_LIBRARY_ID="..."
export ZOTERO_LIBRARY_TYPE="user"  # or group
```

Then use:

- `zotero_search_items` to check existing library records;
- `zotero_get_item` to inspect a record;
- `zotero_create_collection` to organize a project;
- `zotero_add_by_doi` to import searched papers into Zotero;
- `zotero_update_item_tags` to maintain project tags.

## LaTeX and docx configuration

LaTeX compilation uses a local command:

```bash
export LATEX_CMD="latexmk"          # or pdflatex
export LATEX_TIMEOUT_SECONDS="300"
```

Word/docx support uses `python-docx`, installed with the project dependencies.

## Local development

```bash
uv venv
uv pip install -e ".[all]" pytest pytest-asyncio ruff
.venv/Scripts/python scripts/vendor_external_mcps.py pfc-mcp
PYTHONPATH=src .venv/Scripts/python -m pytest tests/ -v
```

## Upstream MCP source internalization

COMSOL / Fluent / PFC support should not be expanded by guessing new wrappers. Use the upstream audit workflow first:

```bash
.venv/Scripts/python scripts/vendor_external_mcps.py --list
.venv/Scripts/python scripts/vendor_external_mcps.py pfc-mcp ansys-mcp-server comsol-multiphysics-mcp comsol-mcp
.venv/Scripts/python scripts/audit_external_mcps.py
```

Vendored repositories under `vendors/external/` are for reading, provenance tracking, and selective porting only. They must not be proxied through runtime MCP bridge tools.

Priority order:

1. audit and port useful PFC Python/API integration;
2. audit and port PyAnsys/PyFluent session and export helpers;
3. compare both COMSOL MCPs and port maintainable COMSOL API / LiveLink / MPh logic.

## MCP config example

```json
{
  "mcpServers": {
    "engineering-research-mcp": {
      "command": "python",
      "args": ["-m", "research_mcp.server"],
      "type": "stdio",
      "env": {
        "PYTHONPATH": "D:/path/to/research-mcp-aggregator/src",
        "COMSOL_CMD": "comsol",
        "FLUENT_CMD": "fluent",
        "PFC_CMD": "pfc",
        "LATEX_CMD": "latexmk",
        "ZOTERO_API_KEY": "your-zotero-key",
        "ZOTERO_LIBRARY_ID": "your-library-id",
        "ZOTERO_LIBRARY_TYPE": "user"
      }
    }
  }
}
```

Do not add separate MCP server configs for Zotero, arXiv, COMSOL, Fluent, PFC, LaTeX, docx, or visualization. Use the internal `research-mcp` tools listed above.

## Next engineering-specific adapters

Good next adapters include:

- Materials Project / thermophysical property databases;
- CFD post-processing for residuals, force coefficients, and convergence plots;
- COMSOL result-table extraction;
- Fluent case/data metadata inspection;
- PFC particle statistics and fracture-network analysis;
- richer LaTeX manuscript assembly and Nature-style figure workflows.
