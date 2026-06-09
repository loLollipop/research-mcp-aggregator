<div align="center">

# Engineering Research MCP

**One local MCP server for engineering research automation.**

Search papers, parse PDFs, manage Zotero records, orchestrate simulations, plot results,
and prepare manuscript assets from a single MCP endpoint.

[简体中文](#中文说明) | **English**

[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![CI](https://github.com/loLollipop/research-mcp-aggregator/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/loLollipop/research-mcp-aggregator/actions/workflows/ci.yml)
[![Release](https://img.shields.io/badge/release-v0.1.0-blue.svg)](https://github.com/loLollipop/research-mcp-aggregator/releases)
[![Python](https://img.shields.io/badge/python-3.10--3.12-3776AB.svg)](pyproject.toml)
[![MCP](https://img.shields.io/badge/MCP-research--mcp-purple.svg)](https://modelcontextprotocol.io/)
[![Stars](https://img.shields.io/github/stars/loLollipop/research-mcp-aggregator?style=social)](https://github.com/loLollipop/research-mcp-aggregator/stargazers)
[![Forks](https://img.shields.io/github/forks/loLollipop/research-mcp-aggregator?style=social)](https://github.com/loLollipop/research-mcp-aggregator/forks)

`v0.1.0 public beta` · stable local utilities and public API workflows are usable today;
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

---

# 中文说明

<div align="center">

**一个面向工程科研自动化的本地 MCP Server。**

把文献检索、PDF 解析、Zotero、仿真流程、结果解析、绘图和论文资产准备整合到一个 MCP 入口。

**当前状态：** `v0.1.0 public beta`。本地工具和公共 API 工作流可用；COMSOL、Fluent、PFC 的 live control 仍是实验性能力。

</div>

## 功能概览

| 方向 | 能力 |
| --- | --- |
| 文献 | arXiv、Semantic Scholar、OpenAlex、Zotero |
| PDF | MinerU 解析，输出 Markdown、分页文本、标题、表格、公式和图注 |
| 仿真 | COMSOL、Fluent、PFC 的规划、fallback、live adapter 和结果解析 |
| 写作 | BibTeX、LaTeX、docx、Nature-style 规划 |
| 图表 | Matplotlib SVG/PNG/PDF |

## 快速安装

```bash
git clone https://github.com/loLollipop/research-mcp-aggregator.git
cd research-mcp-aggregator
uv venv
uv pip install -e .
```

启动：

```bash
research-mcp
```

开发模式：

```bash
python -m research_mcp.server
```

## 常用配置

```bash
export MINERU_API_TOKEN="..."
export ZOTERO_API_KEY="..."
export ZOTERO_LIBRARY_ID="..."
export ZOTERO_LIBRARY_TYPE="user"
export COMSOL_CMD="comsol"
export FLUENT_CMD="fluent"
export PFC_CMD="pfc"
export LATEX_CMD="latexmk"
```

只配置你实际需要的部分即可。

## 常用工具

| 场景 | 工具 |
| --- | --- |
| 文献综述规划 | `research_literature_review_plan` |
| PDF 解析 | `pdf_extract_mineru` |
| 文献库管理 | `zotero_*` |
| 仿真研究规划 | `research_simulation_study_plan` |
| 仿真结果解析 | `comsol_parse_table`, `fluent_parse_residuals`, `pfc_parse_history` |
| 绘图 | `plot_xy`, `plot_csv_columns` |
| 论文资产 | `latex_*`, `docx_*`, `nature_*` |

## 边界

- live solver control 依赖本机商业软件、许可证和进程状态；
- MinerU 解析会把 PDF 上传到 MinerU 服务，请只处理允许外部解析的文件；
- public beta 阶段工具 schema 仍可能调整。

## License

MIT。COMSOL、ANSYS Fluent、PFC 等商业软件不包含在本项目中。
