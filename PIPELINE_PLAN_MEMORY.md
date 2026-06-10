# Adaptive Memory/RAG Pipeline Plan

## Scope

Add a local long-term memory layer to `research-mcp` so agents can persist and retrieve reusable research experience from conversations, simulation runs, Zotero notes, and web sources.

## Units

| unit_id | unit_name | objective | status |
| --- | --- | --- | --- |
| M001 | Memory store | Implement SQLite persistence, search, feedback, and status updates. | DONE |
| M002 | MCP adapter | Expose memory tools through the adapter registry. | DONE |
| M003 | Tests | Cover store behavior, adapter registration, and tool schemas. | DONE |
| M004 | Documentation | Document daily, simulation, Zotero, and web-memory workflows. | DONE |
| M005 | Verification | Run focused tests and record results. | DONE |

## Quality gates

- Memory store initializes without optional dependencies.
- Search uses confidence, status, source, and feedback-aware ranking.
- Web records default to draft/low-confidence unless explicitly promoted.
- Existing MCP schema validation tests continue to pass.
- Documentation explains the system is RAG/experience-memory, not model-weight training.
