# Long-term Memory / RAG Adapter

The `memory` adapter adds a local, lightweight experience store to `research-mcp`.
It is designed to make an MCP client feel more adaptive over time by preserving
reusable research knowledge from conversations, simulation runs, Zotero notes,
web sources, and explicit feedback.

This is not model-weight training or true reinforcement learning. It is a
retrieval-augmented experience loop: record evidence, retrieve similar cases,
apply the best-ranked memory, and update confidence from outcomes.

## Storage

The first implementation uses SQLite plus optional SQLite FTS5. It does not add
heavy vector database dependencies.

Default database path:

```text
.research_mcp/memory.sqlite3
```

Override it with either adapter config or an environment variable:

```bash
export RESEARCH_MCP_MEMORY_DB="D:/path/to/research-memory.sqlite3"
```

## Tools

| Tool | Purpose |
| --- | --- |
| `memory_status` | Inspect database path, item counts, and FTS availability. |
| `memory_record` | Store a general note, preference, workflow, or reusable experience. |
| `memory_search` | Retrieve matching memories with confidence/status/source/feedback ranking. |
| `memory_get` | Fetch a complete memory item and feedback history by id. |
| `memory_export_context` | Generate prompt-ready context from the most relevant memories. |
| `memory_record_simulation_run` | Store a PFC, COMSOL, or Fluent run with parameters and outcome. |
| `memory_record_error_case` | Store an error signature, likely cause, and working fix. |
| `memory_record_literature_note` | Store a Zotero or literature-derived method, claim, or parameter note. |
| `memory_index_zotero_item` | Convert one Zotero Web API item into draft literature memory. |
| `memory_record_web_source` | Store a web-source summary as draft, low-confidence memory. |
| `memory_record_web_results` | Batch-store web search results as draft, low-confidence memories. |
| `memory_feedback` | Mark a memory as worked, failed, useful, or not useful. |
| `memory_promote` | Promote a memory to `verified` or `approved`. |
| `memory_deprecate` | Keep a memory but remove it from normal retrieval priority. |

## Status and confidence

Every item has a status and confidence score.

| Status | Intended meaning |
| --- | --- |
| `draft` | Captured but not yet verified. Default for web and most new notes. |
| `verified` | Supported by a successful run, reliable source, or repeated use. |
| `approved` | Explicitly accepted by the user as reusable project knowledge. |
| `failed` | Known to have failed in a relevant context. |
| `deprecated` | Superseded or no longer reliable; excluded from normal searches. |

Search ranking considers text match, status, confidence, source type, and
success/failure feedback counts. In general, approved and verified project
experience outranks web-only draft material.

## Daily conversation memory

Use `memory_record` to persist reusable preferences or project conventions:

```json
{
  "title": "Default simulation output layout",
  "content": "Store generated scripts under scripts/ and solver outputs under outputs/.",
  "item_type": "preference",
  "status": "approved",
  "confidence": 0.9,
  "tags": ["workflow", "outputs"]
}
```

Retrieve it later with:

```json
{
  "query": "simulation output layout",
  "limit": 5
}
```

## Simulation troubleshooting loop

When a PFC or COMSOL run fails, a client can:

1. Record the run with `memory_record_simulation_run`.
2. Search similar cases with `memory_search`.
3. Try a retrieved fix.
4. Record `memory_feedback` as `worked` or `failed`.
5. Promote the item if it becomes reliable.

Example error case:

```json
{
  "title": "PFC packing unstable after ball distribute",
  "software": "PFC",
  "problem": "Unbalanced force remains high after particle generation.",
  "cause": "Initial porosity was too low, creating excessive overlaps.",
  "fix": "Increase porosity, apply calm cycles, and compact with wall servo gradually.",
  "status": "verified",
  "confidence": 0.8,
  "tags": ["PFC", "packing", "porosity", "unbalanced_force"]
}
```

## Zotero and literature notes

The memory adapter does not replace Zotero. A typical workflow is:

1. Use `zotero_search_items` or `zotero_get_item`.
2. Extract a concise method, parameter, or claim.
3. Store it with `memory_record_literature_note` and preserve `zotero_key` or `doi`.

For a quick first-pass index, pass the raw Zotero Web API item to
`memory_index_zotero_item`. The tool extracts title, creators, date, DOI, URL,
abstract, and Zotero tags into a draft literature memory. Use this for discovery;
promote only concise, checked claims or methods that you expect to reuse.

Example:

```json
{
  "title": "DEM coupling timestep guideline",
  "content": "The paper recommends keeping the coupling timestep below the characteristic contact response time for stable DEM-fluid coupling.",
  "zotero_key": "ABCD1234",
  "doi": "10.0000/example",
  "status": "draft",
  "confidence": 0.55,
  "tags": ["DEM", "coupling", "timestep"]
}
```

## Web-source memory

Use `memory_record_web_source` for web summaries. These default to draft and low
confidence because web material may be incomplete, outdated, or wrong. Promote a
web-derived item only after user review, a reliable source check, or successful
simulation validation.

For search-result pages, `memory_record_web_results` accepts a bounded list of
results with `title`, `url`, and optional `snippet` or `content`. Each result is
stored as a draft web-source memory with the original `search_query` preserved in
metadata for traceability.

## Prompt-ready retrieval

`memory_export_context` returns compact Markdown that an MCP client can insert
into a task prompt before planning or editing:

```json
{
  "query": "COMSOL mesh failure narrow fracture",
  "software": "COMSOL",
  "limit": 5
}
```

## Safety boundary

- The memory database may contain project-sensitive notes. Store it in a location
  appropriate for your project confidentiality requirements.
- Prefer `draft` for uncertain or web-derived information.
- Prefer `verified` for simulation-backed knowledge.
- Prefer `approved` only after human review.
- Deprecate bad memories instead of deleting them so future agents can avoid
  repeating known failed strategies.
