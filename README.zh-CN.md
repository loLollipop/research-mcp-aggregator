<div align="center">

<img src="assets/logo.svg" alt="Engineering Research MCP logo" width="128" />

# Engineering Research MCP

**一个面向工程科研流程的本地 MCP Server。**

通过一个 MCP 入口完成文献检索、PDF 解析、Zotero 管理、本地仿真软件调用、
结果绘图和论文资产准备。

[English](README.md) | **简体中文**

[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![CI](https://github.com/loLollipop/research-mcp-aggregator/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/loLollipop/research-mcp-aggregator/actions/workflows/ci.yml)
[![Release](https://img.shields.io/badge/release-v0.1.0-blue.svg)](https://github.com/loLollipop/research-mcp-aggregator/releases)
[![Python](https://img.shields.io/badge/python-3.10--3.12-3776AB.svg)](pyproject.toml)
[![MCP](https://img.shields.io/badge/MCP-research--mcp-purple.svg)](https://modelcontextprotocol.io/)
[![Stars](https://img.shields.io/github/stars/loLollipop/research-mcp-aggregator?style=social)](https://github.com/loLollipop/research-mcp-aggregator/stargazers)
[![Forks](https://img.shields.io/github/forks/loLollipop/research-mcp-aggregator?style=social)](https://github.com/loLollipop/research-mcp-aggregator/forks)

`v0.1.0 public beta` - 本地工具和公共 API 工作流当前可用；COMSOL、Fluent、
PFC 的 live control 仍是实验性能力。

</div>

---

## 它能做什么

`research-mcp` 用一个本地 MCP Server 取代一组分散的科研 MCP 小工具。

| 方向 | 内置能力 |
| --- | --- |
| 文献 | arXiv、Semantic Scholar、OpenAlex、Zotero Web API |
| PDF 阅读 | MinerU 解析到 Markdown、分页文本、标题、表格、公式和图注 |
| 仿真 | COMSOL、Fluent、PFC 的规划、batch fallback、live adapter 和结果解析 |
| 写作 | BibTeX 辅助、LaTeX 编译/校验、Word/docx 编辑 |
| 图表 | 基于数组或 CSV 列生成 Matplotlib SVG/PNG/PDF 图 |
| 规划 | 文献综述、仿真研究、论文资产包和 Nature-style 规划 |

配置一次 `research-mcp` 后，就可以直接调用 `arxiv_search`、
`pdf_extract_mineru`、`zotero_add_by_doi`、`comsol_parse_table`、`plot_xy`、
`latex_compile`、`docx_create` 等工具。

### 仿真模块定位

仿真相关工具的定位是给 Codex、Claude、Cursor 等编程助手提供一个更高效的
本地求解器控制入口，而不是替代 COMSOL、ANSYS Fluent、PFC 本身，也不是替代
专家验证。它们帮助助手检查文件、用 `dry_run` 预检 batch 命令、调用原生求解器
API 或 bridge 会话、解析导出的表格/日志，并整理可复现的数值模拟过程。

模型设置、单位、材料、边界条件、网格或时间步敏感性、收敛判据和最终物理解释，
仍需要在原生求解器和研究者审查流程中确认。

---

## 安装

要求：Python 3.10-3.12 和 `uv`。

```bash
git clone https://github.com/loLollipop/research-mcp-aggregator.git
cd research-mcp-aggregator
uv venv
uv pip install -e .
```

可选 extras：

```bash
uv pip install -e ".[all]"      # 所有非开发可选集成
uv pip install -e ".[dev]"      # 测试、lint、build 工具
uv pip install -e ".[comsol]"   # COMSOL MPh 后端
uv pip install -e ".[fluent]"   # PyFluent 后端
uv pip install -e ".[pfc]"      # PFC bridge websocket 客户端
```

启动服务：

```bash
research-mcp
# 或
python -m research_mcp.server
```

---

## MCP 客户端配置

已安装包的最小配置：

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

开发目录配置：

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

只配置你实际需要的环境变量即可。

---

## 工具地图

| 分组 | 工具 |
| --- | --- |
| 工作流 | `research_capability_list`, `research_literature_review_plan`, `research_simulation_study_plan`, `research_paper_asset_pack` |
| 迁移目录 | `external_mcp_list`, `external_mcp_get`, `external_mcp_config_snippet`, `engineering_workflow_template` |
| 文献 API | `arxiv_*`, `s2_*`, `openalex_*` |
| PDF / MinerU | `pdf_check_config`, `pdf_extract_mineru` |
| Zotero | `zotero_status`, `zotero_search_items`, `zotero_get_item`, `zotero_create_collection`, `zotero_add_by_doi`, `zotero_update_item_tags` |
| 仿真 | `simulation_check_config`, `simulation_workflow_template`, `comsol_*`, `fluent_*`, `pfc_*` |
| PFC 文档 | `pfc_docs_status`, `pfc_browse_commands`, `pfc_query_command`, `pfc_browse_python_api`, `pfc_query_python_api` |
| 图表 | `plot_xy`, `plot_csv_columns` |
| 写作 | `format_bibtex`, `generate_citation_key`, `parse_bibtex` |
| 论文 | `latex_*`, `docx_*`, `nature_*` |

---

## 配置说明

### MinerU PDF 解析

```bash
export MINERU_API_TOKEN="..."
```

`pdf_extract_mineru` 会把本地 PDF 上传到 MinerU，下载结果压缩包，并写入：

- `outputs/mineru/<paper>/raw/`
- `outputs/mineru/<paper>/pages/page_*.txt`
- `outputs/mineru/<paper>/manifest.json`
- 可选的 `outputs/pdf_pages/page_*.txt` 和 `paper_sections_extract.txt`

扫描版 PDF 可使用 `ocr=true`，局部解析可使用 `page_ranges="8-19"`。

### Zotero

```bash
export ZOTERO_API_KEY="..."
export ZOTERO_LIBRARY_ID="..."
export ZOTERO_LIBRARY_TYPE="user"  # 或 group
```

Zotero 写入类工具会修改已配置的 Zotero library。

### COMSOL / Fluent / PFC

```bash
export COMSOL_CMD="/path/to/comsol"
export FLUENT_CMD="/path/to/fluent"
export PFC_CMD="/path/to/pfc"
export SIM_TIMEOUT_SECONDS="3600"
```

稳定的仿真工具包括规划、文件检查、导出表格解析和绘图。Live solver 会话依赖本机
商业软件、许可证和进程状态。`comsol_run_batch`、`fluent_run_journal`、
`pfc_run_script` 等 batch 工具支持 `dry_run=true`，便于助手在消耗 license 或修改
求解器状态前先检查解析后的命令。

PFC GUI bridge 工作流需要在 GUI 进程中启动 bridge：

```python
import pfc_mcp_bridge

pfc_mcp_bridge.start()
```

---

## 成熟度

| 等级 | 含义 |
| --- | --- |
| 稳定本地工具 | 确定性的文件、解析器、绘图、BibTeX、LaTeX、docx 和导出表格工具 |
| 稳定 API 工作流 | arXiv、OpenAlex、Semantic Scholar、Zotero、MinerU 等网络/API 工作流 |
| 实验性 live solver | 需要本机安装和许可证的 COMSOL MPh、PyFluent、PFC bridge 控制 |
| 迁移辅助 | 帮助替代原本分散 MCP Server 的兼容工具 |

---

## 开发

```bash
uv venv
uv pip install -e ".[all,dev]"
python -m pytest -q
python -m ruff check .
python -m build
```

开发目录中的 PFC 文档浏览需要 vendor 文档资源：

```bash
python scripts/vendor_external_mcps.py pfc-mcp
```

---

## 边界

- Live COMSOL、Fluent、PFC control 是实验性能力，不能替代厂商侧验证。
- 公共学术 API 可能限流，元数据也可能不完整。
- MinerU 解析会把 PDF 上传到配置的 MinerU 服务，请只处理允许外部解析的文件。
- Public beta 阶段工具 schema 仍可能调整。

---

## License

MIT。COMSOL、ANSYS Fluent、PFC 等商业软件不包含在本项目中。
