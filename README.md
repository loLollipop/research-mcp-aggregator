<div align="center">

<img src="assets/logo.svg" alt="Engineering Research MCP logo" width="128" />

# Engineering Research MCP

**One local MCP server for engineering research workflows.**

Search papers, parse PDFs, manage Zotero records, drive local simulation software,
plot results, and prepare manuscript assets from a single MCP endpoint.

**English** | [简体中文](README.zh-CN.md)

[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![CI](https://github.com/loLollipop/research-mcp-aggregator/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/loLollipop/research-mcp-aggregator/actions/workflows/ci.yml)
[![Release](https://img.shields.io/badge/release-v0.1.0-blue.svg)](https://github.com/loLollipop/research-mcp-aggregator/releases)
[![Python](https://img.shields.io/badge/python-3.10--3.12-3776AB.svg)](pyproject.toml)
[![MCP](https://img.shields.io/badge/MCP-research--mcp-purple.svg)](https://modelcontextprotocol.io/)
[![Stars](https://img.shields.io/github/stars/loLollipop/research-mcp-aggregator?style=social)](https://github.com/loLollipop/research-mcp-aggregator/stargazers)
[![Forks](https://img.shields.io/github/forks/loLollipop/research-mcp-aggregator?style=social)](https://github.com/loLollipop/research-mcp-aggregator/forks)

`v0.1.0 public beta` - stable local utilities and public API workflows are usable today;
live COMSOL, Fluent, and PFC control is experimental.

</div>

---

## What it does

`research-mcp` replaces a pile of small research MCP servers with one local server.

| Area | Built-in capability |
| --- | --- |
| Literature | arXiv, Semantic Scholar, OpenAlex, Zotero Web API |
| PDF reading | MinerU extraction to Markdown, page text, headings, tables, formulas, captions |
| Simulation | COMSOL, Fluent, PFC planning, batch fallbacks, live adapters, result parsers |
| Writing | BibTeX helpers, LaTeX compile/validation, Word/docx editing |
| Figures | Matplotlib SVG/PNG/PDF plots from arrays or CSV columns |
| Planning | Literature-review, simulation-study, paper-asset, and Nature-style plans |

Configure `research-mcp` once, then call tools directly such as `arxiv_search`,
`pdf_extract_mineru`, `zotero_add_by_doi`, `comsol_parse_table`, `plot_xy`,
`latex_compile`, or `docx_create`.

### Simulation philosophy

The simulation tools are an assistant-facing control surface for installed local
solvers, not a replacement for COMSOL, ANSYS Fluent, PFC, or expert validation.
They help Codex, Claude, Cursor, and other MCP clients inspect files, preflight
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
        "COMSOL_CMD": "comsol",
        "FLUENT_CMD": "fluent",
        "PFC_CMD": "pfc",
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
| Literature APIs | `arxiv_*`, `s2_*`, `openalex_*` |
| PDF / MinerU | `pdf_check_config`, `pdf_extract_mineru` |
| Zotero | `zotero_status`, `zotero_search_items`, `zotero_get_item`, `zotero_create_collection`, `zotero_add_by_doi`, `zotero_update_item_tags` |
| Simulation | `simulation_check_config`, `simulation_workflow_template`, `comsol_*`, `fluent_*`, `pfc_*` |
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

---

## Maturity

| Level | Meaning |
| --- | --- |
| Stable local | deterministic file, parser, plotting, BibTeX, LaTeX, docx, and exported-table utilities |
| Stable API-backed | arXiv, OpenAlex, Semantic Scholar, Zotero, and MinerU workflows with normal network/API caveats |
| Experimental live solver | COMSOL MPh, PyFluent, and PFC bridge control requiring local installs and licenses |
| Migration helpers | compatibility tools for replacing previously separate MCP servers |

---

## Development

```bash
uv venv
uv pip install -e ".[all,dev]"
python -m pytest -q
python -m ruff check .
python -m build
```

PFC documentation browsing needs vendored docs in development checkouts:

```bash
python scripts/vendor_external_mcps.py pfc-mcp
```

---

## Limitations

- Live COMSOL, Fluent, and PFC control is experimental and not a substitute for vendor-side validation.
- Public scholarly APIs can be rate-limited or return incomplete metadata.
- MinerU parsing uploads PDFs to the configured MinerU service; use it only for files you are allowed to process externally.
- Public beta tool schemas may change before a stable release.

---

## License

MIT. Commercial solvers such as COMSOL, ANSYS Fluent, and PFC are not included.
