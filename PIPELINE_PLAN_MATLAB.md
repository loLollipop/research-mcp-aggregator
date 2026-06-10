# MATLAB MCP Integration Pipeline Plan

## Scope

Add MATLAB support to `research-mcp` as a local self-contained adapter inspired by existing MATLAB MCP implementations, especially the official MathWorks MATLAB MCP Core Server. The adapter ports the core execution capabilities without vendoring third-party server code and adds deterministic post-processing helpers for MATLAB-exported tables and plot-export scripts.

## Source scan

- Official MathWorks project: `matlab/matlab-mcp-core-server`, with core tools for MATLAB code checking, code evaluation, file execution, MATLAB test execution, and toolbox detection.
- Community projects found: `WilliamCloudQi/matlab-mcp-server`, `Tsuchijo/matlab-mcp`, and `neuromechanist/matlab-mcp-tools`.
- Integration decision: implement native Python adapter using MATLAB command-line `-batch` workflows first; do not copy external source code into this repository.
- Local extension: include pure-Python parsing for MATLAB-exported CSV/TSV/TXT tables and generation of reviewed MATLAB plot-export scripts.

## Units

| unit_id | unit_name | objective | status |
| --- | --- | --- | --- |
| ML001 | MATLAB adapter | Add local MATLAB command-line adapter, table parser, plot-export script helper, and tool schemas. | DONE |
| ML002 | Adapter registration | Register MATLAB adapter and all MATLAB tools in discovery and capability catalog. | DONE |
| ML003 | Tests | Add focused MATLAB adapter tests for execution dry-runs, table parsing, plot script generation, and schema compatibility. | DONE |
| ML004 | Documentation | Update README, catalog, tracking files, and run log with MATLAB support and provenance. | DONE |
| ML005 | Verification | Run ruff and focused tests. | DONE |

## Quality gates

- Tool schemas remain valid strict MCP object schemas.
- MATLAB execution tools support dry-run to avoid accidental license/state usage.
- Command construction avoids shell interpolation and uses bounded timeouts.
- Direct Python calls enforce schema-level choices for delimiters and plot kinds.
- Focused adapter/schema tests pass without requiring MATLAB to be installed.
