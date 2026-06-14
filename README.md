<div align="center">

<img src="assets/logo.svg" alt="Engineering Research MCP logo" width="128" />

# Engineering Research MCP

**One local MCP server for engineering research workflows.**

Search papers, parse PDFs, manage Zotero records, drive local simulation software,
plot results, and prepare manuscript assets from a single MCP endpoint.

**English** | [简体中文](README.zh-CN.md)

<p>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License: MIT" /></a>
  <a href="https://github.com/loLollipop/research-mcp-aggregator/actions/workflows/ci.yml"><img src="https://github.com/loLollipop/research-mcp-aggregator/actions/workflows/ci.yml/badge.svg?branch=main" alt="CI" /></a>
  <a href="https://github.com/loLollipop/research-mcp-aggregator/releases"><img src="https://img.shields.io/badge/release-v0.1.0-blue.svg" alt="Release v0.1.0" /></a>
</p>
<p>
  <a href="pyproject.toml"><img src="https://img.shields.io/badge/python-3.10--3.12-3776AB.svg" alt="Python 3.10-3.12" /></a>
  <a href="https://modelcontextprotocol.io/"><img src="https://img.shields.io/badge/MCP-research--mcp-purple.svg" alt="MCP research-mcp" /></a>
</p>

</div>

---

## What it does

`research-mcp` brings common engineering research workflow tools into one local server.

| Area | Built-in capability |
| --- | --- |
| Literature | arXiv, Semantic Scholar, OpenAlex, Zotero Web API |
| Memory / RAG | Local SQLite long-term memory for reusable notes, simulation experience, literature notes, web-source drafts, and feedback-aware retrieval |
| PDF reading | MinerU extraction to Markdown, page text, headings, tables, formulas, captions |
| Simulation | COMSOL, Fluent, PFC, MATLAB planning, batch fallbacks, live adapters, result parsers |
| Writing | BibTeX helpers, LaTeX compile/validation, Word/docx editing |
| Figures | Matplotlib SVG/PNG/PDF plots from arrays or CSV columns |
| OriginLab | Windows Origin/OriginPro worksheet import, graph creation, styling, image export, and LabTalk escape hatch |
| Planning | Literature-review, simulation-study, paper-asset, and Nature-style plans |

Configure `research-mcp` once, then call tools directly such as `arxiv_search`,
`pdf_extract_mineru`, `zotero_add_by_doi`, `memory_search`,
`comsol_parse_table`, `matlab_run_file`, `origin_create_plot`, `plot_xy`,
`latex_compile`, or `docx_create`.

### Simulation philosophy

The simulation tools are an assistant-facing control surface for installed local
solvers, not a replacement for COMSOL, ANSYS Fluent, PFC, or expert validation.
They help MCP clients and AI coding assistants inspect files, preflight
batch commands with `dry_run`, drive native solver APIs or bridge sessions, parse
exported tables/logs, and organize reproducible numerical-study artifacts.

Model setup, units, materials, boundary conditions, mesh or timestep sensitivity,
solver convergence, and final physical interpretation remain in the native solver
and researcher review loop.

---

## Install

Requirements: Python 3.10-3.12 and `uv`.

```bash
git clone https://github.com/loLollipop/research-mcp-aggregator.git
cd research-mcp-aggregator
uv venv
uv pip install -e .
```

Optional extras:

```bash
uv pip install -e ".[all]"      # all optional non-dev integrations
uv pip install -e ".[dev]"      # test/lint/build tools
uv pip install -e ".[comsol]"   # COMSOL MPh backend
uv pip install -e ".[fluent]"   # PyFluent backend
uv pip install -e ".[pfc]"      # PFC bridge websocket client
uv pip install -e ".[origin]"   # OriginLab Origin/OriginPro automation on Windows
```

Start the server:

```bash
research-mcp
# or
python -m research_mcp.server
```

---

## MCP client config

Minimal installed-package config:

```json
{
  "mcpServers": {
    "research-mcp": {
      "command": "research-mcp",
      "type": "stdio"
    }
  }
}
```

Development checkout config:

```json
{
  "mcpServers": {
    "research-mcp": {
      "command": "python",
      "args": ["-m", "research_mcp.server"],
      "type": "stdio",
      "env": {
        "PYTHONPATH": "D:/path/to/research-mcp-aggregator/src",
        "MINERU_API_TOKEN": "your-mineru-token",
        "ZOTERO_API_KEY": "your-zotero-key",
        "ZOTERO_LIBRARY_ID": "your-library-id",
        "ZOTERO_LIBRARY_TYPE": "user",
        "RESEARCH_MCP_MEMORY_DB": "D:/path/to/research-memory.sqlite3",
        "COMSOL_CMD": "comsol",
        "FLUENT_CMD": "fluent",
        "PFC_CMD": "pfc",
        "MATLAB_CMD": "matlab",
        "ORIGIN_EXE": "D:/software/origin/Origin64.exe",
        "ORIGIN_VISIBLE": "1",
        "LATEX_CMD": "latexmk"
      }
    }
  }
}
```

Only set the environment variables for workflows you actually use.

---

## Tool map

| Group | Tools |
| --- | --- |
| Workflows | `research_capability_list`, `research_literature_review_plan`, `research_simulation_study_plan`, `research_paper_asset_pack` |
| Migration catalog | `external_mcp_list`, `external_mcp_get`, `external_mcp_config_snippet`, `engineering_workflow_template` |
| Memory / RAG | `memory_status`, `memory_record`, `memory_search`, `memory_export_context`, `memory_record_simulation_run`, `memory_record_error_case`, `memory_record_literature_note`, `memory_index_zotero_item`, `memory_record_web_source`, `memory_record_web_results`, `memory_feedback`, `memory_promote`, `memory_deprecate` |
| Literature APIs | `arxiv_*`, `s2_*`, `openalex_*` |
| PDF / MinerU | `pdf_check_config`, `pdf_extract_mineru` |
| Zotero | `zotero_status`, `zotero_search_items`, `zotero_get_item`, `zotero_create_collection`, `zotero_add_by_doi`, `zotero_update_item_tags` |
| Simulation | `simulation_check_config`, `simulation_workflow_template`, `comsol_*`, `fluent_*`, `pfc_*` |
| MATLAB | `matlab_check_config`, `matlab_create_script`, `matlab_check_code`, `matlab_evaluate_code`, `matlab_run_file`, `matlab_run_test_file`, `matlab_detect_toolboxes`, `matlab_parse_table`, `matlab_create_plot_export_script` |
| OriginLab | `origin_check_config`, `origin_get_info`, `origin_new_project`, `origin_open_project`, `origin_save_project`, `origin_import_csv`, `origin_list_worksheets`, `origin_create_plot`, `origin_apply_publication_style`, `origin_export_graph`, `origin_execute_labtalk`, `origin_release` |
| PFC docs | `pfc_docs_status`, `pfc_browse_commands`, `pfc_query_command`, `pfc_browse_python_api`, `pfc_query_python_api` |
| Figures | `plot_xy`, `plot_csv_columns` |
| Writing | `format_bibtex`, `generate_citation_key`, `parse_bibtex` |
| Manuscripts | `latex_*`, `docx_*`, `nature_*` |

---

## Configuration notes

### MinerU PDF extraction

```bash
export MINERU_API_TOKEN="..."
```

`pdf_extract_mineru` uploads a local PDF to MinerU, downloads the result archive, and writes:

- `outputs/mineru/<paper>/raw/`
- `outputs/mineru/<paper>/pages/page_*.txt`
- `outputs/mineru/<paper>/manifest.json`
- optionally `outputs/pdf_pages/page_*.txt` and `paper_sections_extract.txt`

Use `ocr=true` for scanned PDFs and `page_ranges="8-19"` for partial extraction.

### Zotero

```bash
export ZOTERO_API_KEY="..."
export ZOTERO_LIBRARY_ID="..."
export ZOTERO_LIBRARY_TYPE="user"  # or group
```

Zotero write tools modify the configured library.

### COMSOL / Fluent / PFC

```bash
export COMSOL_CMD="/path/to/comsol"
export FLUENT_CMD="/path/to/fluent"
export PFC_CMD="/path/to/pfc"
export SIM_TIMEOUT_SECONDS="3600"
```

Stable simulation utilities include planning, file inspection, exported-table parsing, and plotting.
Live solver sessions depend on local commercial software, licenses, and machine state.
Batch tools such as `comsol_run_batch`, `fluent_run_journal`, and `pfc_run_script`
support `dry_run=true` so an assistant can review resolved commands before spending
license time or modifying solver state.

For PFC GUI bridge workflows, start the bridge inside the GUI process:

```python
import pfc_mcp_bridge

pfc_mcp_bridge.start()
```

### MATLAB

```bash
export MATLAB_CMD="/path/to/matlab"
export MATLAB_TIMEOUT_SECONDS="600"
```

The MATLAB adapter is self-contained in Python and uses MATLAB command-line
`-batch` workflows for code checking, code evaluation, file execution,
test-file execution, and toolbox detection. Execution tools default to
`dry_run=true` so commands can be reviewed before consuming license time or
running generated code. It also includes local parsing of MATLAB-exported
CSV/TSV/TXT tables and generation of MATLAB plot-export scripts for reviewed
post-processing workflows.

Minimal local smoke check, if MATLAB is installed and licensed:

```bash
matlab -batch "disp('research-mcp MATLAB smoke')"
python -m pytest -q tests/test_matlab_adapter.py
```

The automated test suite uses dry-run and pure-Python paths by default, so it can
run on GitHub Actions without a MATLAB installation. Live MATLAB execution should
be treated as an optional local validation step before releases.

For release checks, maintainers can run a fuller local smoke that exercises code
evaluation, file execution, `checkcode`, `runtests`, toolbox detection,
MATLAB-exported table parsing, and plot-export script generation. Keep generated
artifacts under `outputs/`, which is ignored by git.

---

## Maturity

| Level | Meaning |
| --- | --- |
| Stable local | deterministic file, parser, plotting, BibTeX, LaTeX, docx, and exported-table utilities |
| Stable API-backed | arXiv, OpenAlex, Semantic Scholar, Zotero, and MinerU workflows with normal network/API caveats |
| Experimental live desktop/solver | COMSOL MPh, PyFluent, PFC bridge, MATLAB, and OriginLab control requiring local installs and licenses |
| Catalog helpers | capability discovery and workflow-template utilities |

---

## Development

```bash
uv venv
uv pip install -e ".[all,dev]"
python -m pytest -q
python -m ruff check .
python -m build
```

Optional PFC documentation browsing uses locally available documentation assets
when present in development checkouts.

---

## Friendly links

- [Linux.do](https://linux.do/)

---

## Limitations

- Live COMSOL, Fluent, and PFC control is experimental and not a substitute for vendor-side validation.
- MATLAB command-line execution is experimental and requires a local MATLAB installation and license.
- OriginLab automation is Windows-only, requires a licensed local Origin/OriginPro installation, and is not a substitute for manual figure review.
- Public scholarly APIs can be rate-limited or return incomplete metadata.
- MinerU parsing uploads PDFs to the configured MinerU service; use it only for files you are allowed to process externally.
- Public beta tool schemas may change before a stable release.

---

## License

MIT.
