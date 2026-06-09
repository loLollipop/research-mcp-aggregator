# Engineering Research MCP

> A self-contained Model Context Protocol (MCP) server for engineering research workflows: literature discovery, Zotero management, COMSOL/PFC/Fluent orchestration, result parsing, figure generation, LaTeX/docx assets, and manuscript planning in one local server.

**Status:** `v0.1.0` research preview / public beta.

Stable local workflows are ready for early users. Live control of commercial solvers is experimental and depends on local installations, licenses, and machine-specific solver state.

Languages: **English** | [中文](#中文说明)

---

## Why this project exists

Engineering researchers rarely work in one tool. A typical study may require:

1. searching papers and tracking evidence;
2. organizing useful references in Zotero;
3. running or managing COMSOL, PFC, or Fluent simulations;
4. parsing exported solver tables and convergence histories;
5. turning data into publication-ready figures;
6. preparing BibTeX, LaTeX, Word reports, and manuscript assets.

`research-mcp` provides one MCP server that exposes these capabilities through local adapters. The goal is not to replace commercial solvers or reference managers, but to make research automation easier to compose from AI assistants such as Cursor, Claude Desktop, or other MCP-compatible clients.

---

## Key features

- **One server, many research tasks**: no need to configure separate MCP servers for arXiv, Zotero, COMSOL, Fluent, PFC, LaTeX, docx, or plotting.
- **Literature workflow tools**: arXiv, Semantic Scholar, OpenAlex, citation planning, and Zotero Web API integration.
- **Engineering simulation workflows**: planning, file inspection, CLI fallbacks, COMSOL MPh sessions, Fluent/PyFluent sessions, PFC bridge execution, and exported table parsing.
- **PFC documentation tools**: command and Python API browsing/search through vendored `pfc-mcp` resources when available.
- **Figure and manuscript assets**: Matplotlib plots, BibTeX helpers, LaTeX compilation, Word/docx creation, and Nature-style manuscript/figure planning.
- **Migration helpers**: `external_mcp_*` tools map formerly separate MCP needs to internal `research-mcp` capabilities.

---

## Capability maturity

`research-mcp` separates stable local utilities from experimental live integrations so users do not confuse parser/workflow coverage with live solver validation.

| Maturity | Meaning | Examples |
| --- | --- | --- |
| Stable | Deterministic local tools or public API integrations | arXiv/OpenAlex/Semantic Scholar search, Zotero metadata operations, BibTeX utilities, Matplotlib figures, LaTeX/docx helpers, exported table parsers |
| Experimental | Live engineering software control that depends on local installation, license, optional Python packages, and process state | COMSOL MPh sessions, PyFluent sessions, live PFC bridge execution |
| Migration | Compatibility helpers mapping former external MCP servers to internal tools | `external_mcp_*` catalog and compose-plan tools |

---

## Architecture

This project exposes one MCP server: `research-mcp`.

The server uses local adapters:

- literature search calls public APIs such as arXiv, Semantic Scholar, and OpenAlex;
- Zotero integration uses Zotero Web API semantics;
- COMSOL uses an internal MPh backend with a command-line batch fallback;
- Fluent uses an internal PyFluent backend with a command-line journal fallback;
- PFC uses vendored `pfc-mcp` documentation resources and an internal WebSocket bridge backend, with script/history fallback tools;
- figures use Matplotlib and save SVG/PNG/PDF outputs;
- LaTeX uses local `latexmk` or `pdflatex`;
- Word/docx support uses `python-docx`;
- each domain is registered into the same MCP server.

The simulation layer follows an internalization strategy: mature COMSOL / Fluent / PFC MCP repositories may be vendored for source audit and selective porting, but runtime users still configure only one `research-mcp` server.

---

## Quick start

### 1. Install from a source checkout

```bash
git clone https://github.com/loLollipop/research-mcp-aggregator.git
cd research-mcp-aggregator
uv venv
uv pip install -e ".[all]" pytest pytest-asyncio ruff mypy build
```

If you only want the core local tools, install the base package:

```bash
uv pip install -e .
```

Optional extras:

```bash
uv pip install -e ".[comsol]"      # MPh / COMSOL support
uv pip install -e ".[fluent]"      # PyFluent support
uv pip install -e ".[simulation]"  # PFC bridge client dependency
uv pip install -e ".[all]"         # all optional research integrations
```

### 2. Start the MCP server

Installed console script:

```bash
research-mcp
```

Equivalent module entry point:

```bash
python -m research_mcp.server
```

### 3. Configure an MCP client

Installed-package configuration:

```json
{
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
        "ZOTERO_LIBRARY_TYPE": "user"
      }
    }
  }
}
```

Development-from-source configuration:

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

Do **not** add separate MCP server configs for Zotero, arXiv, COMSOL, Fluent, PFC, LaTeX, docx, or visualization. Use the internal `research-mcp` tools listed below.

---

## Tool overview

### Research workflow planners

The `research_*` tools are side-effect-free orchestration helpers. They do not directly search the web, write to Zotero, launch solvers, compile manuscripts, or create figures. They return structured plans that compose lower-level tools.

| Tool | Purpose |
| --- | --- |
| `research_capability_list` | List local capabilities with maturity, dependencies, workflow roles, and output types |
| `research_capability_get` | Inspect one capability by local key or replaced external MCP name |
| `research_literature_review_plan` | Compose paper search, citation expansion, Zotero/library management, and BibTeX synthesis stages |
| `research_simulation_study_plan` | Compose simulation design, live/batch execution, parser, and figure-generation stages |
| `research_paper_asset_pack` | Compose claim-evidence mapping, citation assets, LaTeX/docx manuscript assets, and submission checks |

### Major tool groups

| Module | Tools | Purpose |
| --- | --- | --- |
| Nature manuscript workflows | `nature_manuscript_plan`, `nature_figure_package_plan`, `nature_submission_readiness_checklist` | Plan manuscript narrative, figure packages, evidence maps, reporting, data/code, and submission readiness |
| Internal capability catalog | `external_mcp_list`, `external_mcp_get`, `external_mcp_config_snippet`, `external_mcp_compose_plan`, `engineering_workflow_template` | Map former external MCP needs to local `research-mcp` tools |
| ArXiv | `arxiv_search`, `arxiv_get_paper` | Search preprints and fetch paper metadata |
| Semantic Scholar | `s2_search`, `s2_get_paper`, `s2_get_citations`, `s2_get_references` | Search papers and citation/reference networks |
| OpenAlex | `openalex_search_works`, `openalex_get_work`, `openalex_get_author` | Open scholarly search, work details, and author metadata |
| Zotero | `zotero_status`, `zotero_search_items`, `zotero_get_item`, `zotero_create_collection`, `zotero_add_by_doi`, `zotero_update_item_tags` | Manage literature records and tags through Zotero Web API |
| Simulation | `simulation_check_config`, `simulation_workflow_template`, `comsol_*`, `fluent_*`, `pfc_*` | Plan, run, inspect, parse, and bridge-connect COMSOL, Fluent, and PFC workflows |
| PFC docs | `pfc_docs_status`, `pfc_browse_commands`, `pfc_query_command`, `pfc_browse_python_api`, `pfc_query_python_api` | Browse/search PFC command and Python API docs when vendored resources are available |
| Figure | `plot_xy`, `plot_csv_columns` | Create SVG/PNG/PDF figures from arrays or CSV columns |
| Writing | `format_bibtex`, `generate_citation_key`, `parse_bibtex` | Citation keys and BibTeX formatting/parsing |
| LaTeX | `latex_check_config`, `latex_validate_project`, `latex_compile`, `latex_create_minimal_project` | Validate and compile local LaTeX manuscripts |
| Word/docx | `docx_create`, `docx_read`, `docx_add_heading`, `docx_add_paragraph`, `docx_add_table` | Create, inspect, and update `.docx` reports |

---

## Simulation configuration

Simulation support is split into stable local planning/parsing tools and experimental live solver controls.

Stable local tools include:

- workflow templates;
- solver file inspection;
- exported COMSOL table parsing;
- Fluent residual parsing;
- PFC/DEM history parsing;
- figure generation from parsed data.

Experimental live controls additionally require the corresponding commercial software, a valid local license, optional Python packages, and machine-specific environment setup.

Set command paths as environment variables or in the MCP client config:

```bash
export COMSOL_CMD="/path/to/comsol"
export FLUENT_CMD="/path/to/fluent"
export PFC_CMD="/path/to/pfc"
export SIM_TIMEOUT_SECONDS="3600"
```

On Windows, full executable paths with spaces are supported through MCP environment config.

### COMSOL

Install optional dependencies:

```bash
uv pip install -e ".[comsol]"
```

Live COMSOL control uses the internal MPh backend. The preferred workflow is attach-first: start COMSOL Multiphysics Server manually, then call `comsol_server_connect`. The command-line fallback `comsol_run_batch` only requires `COMSOL_CMD` to point to a usable COMSOL or `comsolbatch` executable.

Representative tools:

- `comsol_check_mph`
- `comsol_server_connect`
- `comsol_model_load`
- `comsol_model_create`
- `comsol_get_parameters`
- `comsol_set_parameters`
- `comsol_solve`
- `comsol_solve_status`
- `comsol_run_batch`
- `comsol_parse_table`

### Fluent

Install optional dependencies:

```bash
uv pip install -e ".[fluent]"
```

Live Fluent control uses PyFluent and local Ansys licensing. The fallback `fluent_run_journal` runs Fluent journals through the configured Fluent executable.

Representative tools:

- `fluent_check_pyfluent`
- `fluent_launch_session`
- `fluent_execute_tui`
- `fluent_list_sessions`
- `fluent_close_session`
- `fluent_run_journal`
- `fluent_parse_residuals`

### PFC

Install the MCP-side WebSocket dependency:

```bash
uv pip install -e ".[simulation]"
```

PFC workflows have three practical modes:

1. **Script / console fallback**: use `pfc_run_script` with a configured PFC command.
2. **Bridge execution**: use `pfc_execute_code`, `pfc_execute_task`, `pfc_check_task_status`, `pfc_list_tasks`, and `pfc_interrupt_task` after a bridge is running.
3. **PFC docs browsing**: use vendored `pfc-mcp` resources through `pfc_browse_commands`, `pfc_query_command`, `pfc_browse_python_api`, and `pfc_query_python_api`.

For GUI bridge usage, start the bridge inside the PFC GUI process:

```python
import pfc_mcp_bridge

pfc_mcp_bridge.start()
```

The default bridge URL is `ws://localhost:9001`; override it with `PFC_MCP_BRIDGE_URL` if needed.

Important boundary: a bridge started in a PFC console process controls that console process, not an already-open GUI process. For live GUI visualization, the bridge must be started inside the GUI process itself.

---

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

---

## LaTeX and docx configuration

LaTeX compilation uses a local command:

```bash
export LATEX_CMD="latexmk"          # or pdflatex
export LATEX_TIMEOUT_SECONDS="300"
```

Word/docx support uses `python-docx`, installed with the base project dependencies.

---

## PFC documentation resources

PFC documentation search reads vendored `pfc-mcp` documentation resources when available. In a development checkout, vendor the resources with:

```bash
.venv/Scripts/python scripts/vendor_external_mcps.py pfc-mcp
```

If the resources are absent, PFC docs tools return a structured `docs_not_vendored` response instead of crashing.

---

## Development

```bash
uv venv
uv pip install -e ".[all]" pytest pytest-asyncio ruff mypy build
.venv/Scripts/python scripts/vendor_external_mcps.py pfc-mcp
.venv/Scripts/python -m pytest tests/ -v
```

Useful checks:

```bash
python -m pytest -q
python -m ruff check .
```

Recent validation before public beta cleanup:

- focused simulation/PFC docs tests: `62 passed, 5 skipped`;
- full test suite: `124 passed, 9 skipped`;
- Ruff: all checked files passed.

---

## Upstream MCP source internalization

COMSOL / Fluent / PFC support should not be expanded by guessing wrappers. Use the upstream audit workflow first:

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

---

## Known limitations

- Live COMSOL, Fluent, and PFC control depends on proprietary software, local licensing, and machine-specific environment setup.
- PFC GUI bridge startup is manual unless the user configures their PFC GUI environment to run `pfc_mcp_bridge.start()`.
- A PFC console bridge can be automated, but it controls the console process, not an already-open GUI process.
- PFC documentation tools need vendored documentation resources for full browsing/search coverage.
- This project is currently a research preview / public beta, not a production-certified solver management platform.

---

## Next engineering adapters

Potential future adapters include:

- Materials Project / thermophysical property databases;
- CFD post-processing for residuals, force coefficients, and convergence plots;
- richer COMSOL result-table extraction;
- Fluent case/data metadata inspection;
- PFC particle statistics and fracture-network analysis;
- richer LaTeX manuscript assembly and Nature-style figure workflows.

---

## License

MIT. Commercial solvers such as COMSOL, ANSYS Fluent, and PFC are not included and remain subject to their own licenses.

---

# 中文说明

> 一个面向工程科研工作流的自包含 MCP 服务器：把文献检索、Zotero 文献管理、COMSOL/PFC/Fluent 仿真编排、结果解析、图表生成、LaTeX/docx 资产和论文写作规划整合到一个本地服务中。

**项目状态：** `v0.1.0` research preview / public beta。

本地稳定工具已经适合早期用户试用；商业仿真软件的 live control 属于实验性能力，依赖用户本机软件安装、许可证和运行环境。

---

## 这个项目解决什么问题

工程科研通常不是一个工具就能完成的。一个完整研究可能需要：

1. 搜索论文、整理证据；
2. 把重要文献保存到 Zotero；
3. 运行或管理 COMSOL、PFC、Fluent 仿真；
4. 解析求解器导出的表格、残差和历史曲线；
5. 把数据转换成论文图；
6. 准备 BibTeX、LaTeX、Word 报告和投稿资产。

`research-mcp` 的目标不是替代商业仿真软件或文献管理器，而是提供一个统一的 MCP 入口，让 Cursor、Claude Desktop 或其他 MCP 客户端更容易组合这些科研自动化流程。

---

## 核心特性

- **一个 server 覆盖多个科研环节**：不需要分别配置 arXiv、Zotero、COMSOL、Fluent、PFC、LaTeX、docx、绘图等 MCP server。
- **文献工作流**：支持 arXiv、Semantic Scholar、OpenAlex、Zotero Web API，以及文献综述规划。
- **工程仿真工作流**：支持仿真规划、文件检查、CLI fallback、COMSOL MPh、Fluent/PyFluent、PFC bridge 和导出数据解析。
- **PFC 文档工具**：在 vendored `pfc-mcp` 资源存在时，可浏览/搜索 PFC 命令和 Python API 文档。
- **图表与论文资产**：支持 Matplotlib 图、BibTeX 工具、LaTeX 编译、Word/docx 创建，以及 Nature 风格论文和图表规划。
- **迁移辅助**：`external_mcp_*` 工具把过去需要外部 MCP 的能力映射到当前内部能力。

---

## 能力成熟度

`research-mcp` 明确区分稳定本地工具和实验性 live 集成，避免用户把“能解析文件/能规划流程”误解为“已经完全验证所有商业求解器”。

| 成熟度 | 含义 | 示例 |
| --- | --- | --- |
| Stable | 行为确定的本地工具，或依赖公共 API 的工具 | arXiv/OpenAlex/Semantic Scholar 搜索、Zotero 元数据操作、BibTeX、Matplotlib 图、LaTeX/docx、导出表格解析 |
| Experimental | 依赖本机安装、许可证、可选 Python 包和求解器状态的 live 工程软件控制 | COMSOL MPh session、PyFluent session、PFC bridge live 执行 |
| Migration | 把过去外部 MCP server 映射到内部工具的兼容辅助层 | `external_mcp_*` catalog 和 compose-plan 工具 |

---

## 架构说明

本项目只暴露一个 MCP server：`research-mcp`。

内部通过本地 adapter 提供能力：

- 文献检索直接调用 arXiv、Semantic Scholar、OpenAlex 等公共 API；
- Zotero 使用 Zotero Web API 语义；
- COMSOL 使用内部 MPh backend，并保留命令行 batch fallback；
- Fluent 使用内部 PyFluent backend，并保留 journal 命令行 fallback；
- PFC 使用 vendored `pfc-mcp` 文档资源和内部 WebSocket bridge backend，并保留 script/history fallback；
- 图表使用 Matplotlib 输出 SVG/PNG/PDF；
- LaTeX 调用本地 `latexmk` 或 `pdflatex`；
- Word/docx 使用 `python-docx`；
- 所有能力注册到同一个 MCP server 中。

仿真层采用“上游 MCP 源码内化”的路线：COMSOL / Fluent / PFC 相关成熟 MCP 仓库可以被 vendored 用于审计和选择性移植，但运行时用户仍然只需要配置一个 `research-mcp` server。

---

## 快速开始

### 1. 从源码安装

```bash
git clone https://github.com/loLollipop/research-mcp-aggregator.git
cd research-mcp-aggregator
uv venv
uv pip install -e ".[all]" pytest pytest-asyncio ruff mypy build
```

如果只需要核心本地工具：

```bash
uv pip install -e .
```

可选 extras：

```bash
uv pip install -e ".[comsol]"      # MPh / COMSOL 支持
uv pip install -e ".[fluent]"      # PyFluent 支持
uv pip install -e ".[simulation]"  # PFC bridge client 依赖
uv pip install -e ".[all]"         # 安装所有可选科研集成
```

### 2. 启动 MCP server

安装后的命令行入口：

```bash
research-mcp
```

等价的模块入口：

```bash
python -m research_mcp.server
```

### 3. 配置 MCP 客户端

安装包配置示例：

```json
{
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
        "ZOTERO_LIBRARY_TYPE": "user"
      }
    }
  }
}
```

源码开发配置示例：

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

不要再为 Zotero、arXiv、COMSOL、Fluent、PFC、LaTeX、docx 或绘图单独配置其他 MCP server；这些能力已经集成在 `research-mcp` 内部。

---

## 工具概览

### 科研工作流规划工具

`research_*` 工具是无副作用的编排规划工具。它们不会直接搜索网页、写入 Zotero、启动求解器、编译论文或创建图像，而是返回结构化计划，让下层工具执行具体动作。

| 工具 | 用途 |
| --- | --- |
| `research_capability_list` | 列出本地能力、成熟度、依赖、工作流角色和输出类型 |
| `research_capability_get` | 检查某个能力或被替代的外部 MCP 名称 |
| `research_literature_review_plan` | 组合论文搜索、引文扩展、Zotero 管理和 BibTeX 合成流程 |
| `research_simulation_study_plan` | 组合仿真设计、live/batch 执行、解析和绘图流程 |
| `research_paper_asset_pack` | 组合 claim-evidence map、引用资产、LaTeX/docx 资产和投稿检查 |

### 主要工具组

| 模块 | 工具 | 用途 |
| --- | --- | --- |
| Nature 论文工作流 | `nature_manuscript_plan`, `nature_figure_package_plan`, `nature_submission_readiness_checklist` | 规划论文叙事、图表包、证据链、报告规范、数据/代码和投稿准备度 |
| 内部能力目录 | `external_mcp_list`, `external_mcp_get`, `external_mcp_config_snippet`, `external_mcp_compose_plan`, `engineering_workflow_template` | 把原外部 MCP 需求映射到本地 `research-mcp` 工具 |
| ArXiv | `arxiv_search`, `arxiv_get_paper` | 搜索预印本和获取论文元数据 |
| Semantic Scholar | `s2_search`, `s2_get_paper`, `s2_get_citations`, `s2_get_references` | 搜索论文和引用/参考文献网络 |
| OpenAlex | `openalex_search_works`, `openalex_get_work`, `openalex_get_author` | 开放学术搜索、作品详情和作者元数据 |
| Zotero | `zotero_status`, `zotero_search_items`, `zotero_get_item`, `zotero_create_collection`, `zotero_add_by_doi`, `zotero_update_item_tags` | 通过 Zotero Web API 管理文献记录和标签 |
| Simulation | `simulation_check_config`, `simulation_workflow_template`, `comsol_*`, `fluent_*`, `pfc_*` | 规划、运行、检查、解析和 bridge 连接 COMSOL / Fluent / PFC 工作流 |
| PFC docs | `pfc_docs_status`, `pfc_browse_commands`, `pfc_query_command`, `pfc_browse_python_api`, `pfc_query_python_api` | 在 vendored 资源存在时浏览/搜索 PFC 命令和 Python API 文档 |
| Figure | `plot_xy`, `plot_csv_columns` | 从数组或 CSV 列创建 SVG/PNG/PDF 图 |
| Writing | `format_bibtex`, `generate_citation_key`, `parse_bibtex` | BibTeX 格式化、解析和 citation key 生成 |
| LaTeX | `latex_check_config`, `latex_validate_project`, `latex_compile`, `latex_create_minimal_project` | 验证和编译本地 LaTeX 项目 |
| Word/docx | `docx_create`, `docx_read`, `docx_add_heading`, `docx_add_paragraph`, `docx_add_table` | 创建、检查和更新 `.docx` 报告 |

---

## 仿真配置

仿真支持分为稳定的本地规划/解析工具，以及实验性的 live solver control。

稳定本地工具包括：

- 工作流模板；
- 求解器文件检查；
- COMSOL 导出表格解析；
- Fluent 残差解析；
- PFC/DEM history 解析；
- 从解析数据生成图表。

实验性 live control 还需要对应商业软件、有效许可证、可选 Python 包和本机环境配置。

通过环境变量或 MCP client config 指定命令路径：

```bash
export COMSOL_CMD="/path/to/comsol"
export FLUENT_CMD="/path/to/fluent"
export PFC_CMD="/path/to/pfc"
export SIM_TIMEOUT_SECONDS="3600"
```

Windows 下支持在 MCP 环境配置里传入带空格的完整可执行文件路径。

### COMSOL

安装可选依赖：

```bash
uv pip install -e ".[comsol]"
```

COMSOL live control 使用内部 MPh backend。推荐 attach-first 流程：手动启动 COMSOL Multiphysics Server，然后调用 `comsol_server_connect`。命令行 fallback `comsol_run_batch` 只要求 `COMSOL_CMD` 指向可用的 COMSOL 或 `comsolbatch` 可执行文件。

### Fluent

安装可选依赖：

```bash
uv pip install -e ".[fluent]"
```

Fluent live control 使用 PyFluent 和本机 Ansys 许可。fallback `fluent_run_journal` 通过配置的 Fluent 可执行文件运行 journal。

### PFC

安装 MCP 侧 WebSocket 依赖：

```bash
uv pip install -e ".[simulation]"
```

PFC 有三种实用模式：

1. **Script / console fallback**：通过 `pfc_run_script` 调用配置的 PFC 命令；
2. **Bridge execution**：bridge 已运行后，使用 `pfc_execute_code`、`pfc_execute_task`、`pfc_check_task_status`、`pfc_list_tasks`、`pfc_interrupt_task`；
3. **PFC 文档浏览**：通过 vendored `pfc-mcp` 资源使用 `pfc_browse_commands`、`pfc_query_command`、`pfc_browse_python_api`、`pfc_query_python_api`。

如果要使用 PFC GUI bridge，需要在 PFC GUI 进程内部启动 bridge：

```python
import pfc_mcp_bridge

pfc_mcp_bridge.start()
```

默认 bridge URL 是 `ws://localhost:9001`；如有需要，可用 `PFC_MCP_BRIDGE_URL` 覆盖。

重要边界：在 PFC console 进程中启动的 bridge 只能控制该 console 进程，不能控制已经打开的 GUI 进程。如果需要 GUI 实时可视化，bridge 必须在 GUI 进程内部启动。

---

## Zotero 配置

```bash
export ZOTERO_API_KEY="..."
export ZOTERO_LIBRARY_ID="..."
export ZOTERO_LIBRARY_TYPE="user"  # or group
```

常用工具：

- `zotero_search_items`：检查已有文献；
- `zotero_get_item`：查看单条记录；
- `zotero_create_collection`：创建集合；
- `zotero_add_by_doi`：通过 DOI 导入；
- `zotero_update_item_tags`：维护标签。

---

## LaTeX 和 docx 配置

```bash
export LATEX_CMD="latexmk"          # or pdflatex
export LATEX_TIMEOUT_SECONDS="300"
```

Word/docx 支持基于 `python-docx`，已包含在基础依赖中。

---

## PFC 文档资源

PFC 文档搜索在资源存在时读取 vendored `pfc-mcp` 文档。开发环境可以执行：

```bash
.venv/Scripts/python scripts/vendor_external_mcps.py pfc-mcp
```

如果资源不存在，PFC docs 工具会返回结构化 `docs_not_vendored` 响应，而不是直接崩溃。

---

## 开发与验证

```bash
uv venv
uv pip install -e ".[all]" pytest pytest-asyncio ruff mypy build
.venv/Scripts/python scripts/vendor_external_mcps.py pfc-mcp
.venv/Scripts/python -m pytest tests/ -v
```

常用检查：

```bash
python -m pytest -q
python -m ruff check .
```

public beta 清理前的近期验证：

- focused simulation/PFC docs tests：`62 passed, 5 skipped`；
- full test suite：`124 passed, 9 skipped`；
- Ruff：全部通过。

---

## 已知限制

- COMSOL、Fluent、PFC 的 live control 依赖商业软件、本地许可证和机器环境。
- PFC GUI bridge 默认需要用户手动在 GUI 内执行 `pfc_mcp_bridge.start()`，除非用户自己配置 PFC GUI startup 环境。
- PFC console bridge 可以自动化，但它控制的是 console 进程，不是已打开的 GUI 进程。
- PFC docs 工具需要 vendored 文档资源才能完整浏览和搜索。
- 当前项目是 research preview / public beta，不是生产认证的求解器管理平台。

---

## 许可证

MIT。COMSOL、ANSYS Fluent、PFC 等商业求解器不包含在本项目中，并受各自软件许可证约束。
