# Vendored external MCPs

This directory is for upstream MCP repositories that we inspect before porting mature solver capabilities into `research-mcp`.

Policy:

1. Keep runtime as one local `research-mcp` server.
2. Do not proxy tools from vendored repositories with an MCP bridge.
3. Use vendored source for audit, provenance tracking, and selective porting only.
4. Check license files before copying code or adapting implementation details.
5. Prefer small local backend modules under `src/research_mcp/` over direct upstream imports.

Workflow:

```bash
.venv/Scripts/python scripts/vendor_external_mcps.py --list
.venv/Scripts/python scripts/vendor_external_mcps.py pfc-mcp ansys-mcp-server comsol-multiphysics-mcp comsol-mcp
.venv/Scripts/python scripts/audit_external_mcps.py
```

Current target repos are listed in `external_mcp_sources.json`.
