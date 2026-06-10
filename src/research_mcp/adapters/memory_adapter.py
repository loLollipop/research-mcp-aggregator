"""Long-term memory and lightweight RAG adapter."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from research_mcp.adapters import AdapterMeta, BaseAdapter, ToolSpec, register_adapter
from research_mcp.memory.models import VALID_ITEM_TYPES, VALID_STATUSES
from research_mcp.memory.store import MemoryStore

ITEM_TYPE_ENUM = ["", *sorted(VALID_ITEM_TYPES)]
STATUS_ENUM = ["", *sorted(VALID_STATUSES)]
PROMOTE_STATUS_ENUM = ["verified", "approved"]


def _string_schema(description: str, *, required: bool = False) -> dict[str, Any]:
    schema: dict[str, Any] = {"type": "string", "description": description}
    if required:
        schema["minLength"] = 1
    return schema


def _tags_schema() -> dict[str, Any]:
    return {
        "type": "array",
        "items": {"type": "string"},
        "description": "Optional tags used for filtering and retrieval.",
        "maxItems": 100,
    }


@register_adapter
class MemoryAdapter(BaseAdapter):
    """Persist reusable research experience for later retrieval."""

    adapter_name = "memory"

    def __init__(self) -> None:
        self.store: MemoryStore | None = None
        self.db_path = Path(".research_mcp") / "memory.sqlite3"

    def metadata(self) -> AdapterMeta:
        return AdapterMeta(
            name="memory",
            description="Local long-term memory/RAG store for reusable research experience.",
            tools=[
                ToolSpec(
                    name="memory_status",
                    description="Check local long-term memory store status and counts.",
                    input_schema={"type": "object", "properties": {}},
                    handler=self.status,
                ),
                ToolSpec(
                    name="memory_record",
                    description="Record a reusable note, preference, workflow, or experience.",
                    input_schema={
                        "type": "object",
                        "properties": self._base_record_properties(),
                        "required": ["title", "content"],
                    },
                    handler=self.record,
                ),
                ToolSpec(
                    name="memory_search",
                    description="Search long-term memory with status/confidence-aware ranking.",
                    input_schema={
                        "type": "object",
                        "properties": self._search_properties(),
                        "required": ["query"],
                    },
                    handler=self.search,
                ),
                ToolSpec(
                    name="memory_get",
                    description="Get one complete memory item by id.",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "item_id": _string_schema("Memory item id.", required=True)
                        },
                        "required": ["item_id"],
                    },
                    handler=self.get,
                ),
                ToolSpec(
                    name="memory_export_context",
                    description="Export prompt-ready context from relevant long-term memories.",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "query": _string_schema("Retrieval query.", required=True),
                            "limit": {
                                "type": "integer",
                                "description": "Maximum memories to include.",
                                "default": 5,
                                "minimum": 1,
                                "maximum": 20,
                            },
                            "software": _string_schema("Optional software filter."),
                            "project": _string_schema("Optional project filter."),
                        },
                        "required": ["query"],
                    },
                    handler=self.export_context,
                ),
                ToolSpec(
                    name="memory_record_simulation_run",
                    description="Record a PFC/COMSOL/Fluent run as reusable simulation memory.",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "software": _string_schema("Simulation software.", required=True),
                            "task": _string_schema("Simulation task or case name.", required=True),
                            "status": _string_schema("Run outcome status.", required=True),
                            "parameter_values": {
                                "type": "object",
                                "description": "Structured parameter values for this run.",
                            },
                            "input_files": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Input file paths or identifiers.",
                                "maxItems": 100,
                            },
                            "output_files": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Output file paths or identifiers.",
                                "maxItems": 100,
                            },
                            "log_excerpt": _string_schema("Concise run log excerpt."),
                            "error_signature": _string_schema("Optional error signature."),
                            "fix_item_ids": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Memory ids used as attempted fixes.",
                                "maxItems": 50,
                            },
                        },
                        "required": ["software", "task", "status"],
                    },
                    handler=self.record_simulation_run,
                ),
                ToolSpec(
                    name="memory_record_error_case",
                    description="Record a reusable simulation or workflow error case and fix.",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "title": _string_schema("Short error-case title.", required=True),
                            "software": _string_schema("Related software or tool."),
                            "problem": _string_schema("Observed problem.", required=True),
                            "cause": _string_schema("Suspected or verified cause."),
                            "fix": _string_schema("Fix or mitigation.", required=True),
                            "project": _string_schema("Optional project name."),
                            "source_ref": _string_schema("Run id, URL, paper key, or note ref."),
                            "status": {
                                "type": "string",
                                "enum": STATUS_ENUM,
                                "default": "draft",
                            },
                            "confidence": {
                                "type": "number",
                                "default": 0.5,
                                "minimum": 0,
                                "maximum": 1,
                            },
                            "tags": _tags_schema(),
                        },
                        "required": ["title", "problem", "fix"],
                    },
                    handler=self.record_error_case,
                ),
                ToolSpec(
                    name="memory_record_literature_note",
                    description=(
                        "Record a Zotero or literature-derived claim, method, or "
                        "parameter note."
                    ),
                    input_schema={
                        "type": "object",
                        "properties": {
                            "title": _string_schema("Literature note title.", required=True),
                            "content": _string_schema(
                                "Extracted claim or method note.", required=True
                            ),
                            "zotero_key": _string_schema("Optional Zotero item key."),
                            "doi": _string_schema("Optional DOI."),
                            "project": _string_schema("Optional project name."),
                            "status": {
                                "type": "string",
                                "enum": STATUS_ENUM,
                                "default": "draft",
                            },
                            "confidence": {
                                "type": "number",
                                "default": 0.55,
                                "minimum": 0,
                                "maximum": 1,
                            },
                            "tags": _tags_schema(),
                        },
                        "required": ["title", "content"],
                    },
                    handler=self.record_literature_note,
                ),
                ToolSpec(
                    name="memory_index_zotero_item",
                    description="Index one Zotero Web API item as draft literature memory.",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "item": {
                                "type": "object",
                                "description": "Zotero item JSON from zotero_get_item/search.",
                            },
                            "project": _string_schema("Optional project name."),
                            "status": {
                                "type": "string",
                                "enum": STATUS_ENUM,
                                "default": "draft",
                            },
                            "confidence": {
                                "type": "number",
                                "default": 0.55,
                                "minimum": 0,
                                "maximum": 1,
                            },
                            "tags": _tags_schema(),
                        },
                        "required": ["item"],
                    },
                    handler=self.index_zotero_item,
                ),
                ToolSpec(
                    name="memory_record_web_source",
                    description="Record a web source summary as low-confidence draft memory.",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "title": _string_schema("Web source title.", required=True),
                            "content": _string_schema("Source-grounded summary.", required=True),
                            "source_url": _string_schema("Source URL.", required=True),
                            "project": _string_schema("Optional project name."),
                            "status": {
                                "type": "string",
                                "enum": STATUS_ENUM,
                                "default": "draft",
                            },
                            "confidence": {
                                "type": "number",
                                "default": 0.3,
                                "minimum": 0,
                                "maximum": 1,
                            },
                            "tags": _tags_schema(),
                        },
                        "required": ["title", "content", "source_url"],
                    },
                    handler=self.record_web_source,
                ),
                ToolSpec(
                    name="memory_record_web_results",
                    description="Batch-record web search results as low-confidence draft memories.",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "search_query": _string_schema(
                                "Original web search query.", required=True
                            ),
                            "results": {
                                "type": "array",
                                "description": (
                                    "Search results with title, URL, and optional snippet."
                                ),
                                "minItems": 1,
                                "maxItems": 25,
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "title": {"type": "string", "minLength": 1},
                                        "url": {"type": "string", "minLength": 1},
                                        "snippet": {"type": "string"},
                                        "content": {"type": "string"},
                                    },
                                    "required": ["title", "url"],
                                    "additionalProperties": False,
                                },
                            },
                            "project": _string_schema("Optional project name."),
                            "status": {
                                "type": "string",
                                "enum": STATUS_ENUM,
                                "default": "draft",
                            },
                            "confidence": {
                                "type": "number",
                                "default": 0.3,
                                "minimum": 0,
                                "maximum": 1,
                            },
                            "tags": _tags_schema(),
                        },
                        "required": ["search_query", "results"],
                    },
                    handler=self.record_web_results,
                ),
                ToolSpec(
                    name="memory_feedback",
                    description="Record feedback that raises or lowers memory confidence.",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "item_id": _string_schema("Memory item id.", required=True),
                            "outcome": _string_schema(
                                "Outcome such as worked, failed, useful, or not_useful.",
                                required=True,
                            ),
                            "feedback_type": _string_schema("Feedback category."),
                            "note": _string_schema("Optional feedback note."),
                            "run_ref": _string_schema("Optional run or task reference."),
                            "delta_confidence": {
                                "type": "number",
                                "description": "Optional manual confidence delta.",
                                "minimum": -1,
                                "maximum": 1,
                            },
                        },
                        "required": ["item_id", "outcome"],
                    },
                    handler=self.feedback,
                ),
                ToolSpec(
                    name="memory_promote",
                    description="Promote a memory item to verified or approved status.",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "item_id": _string_schema("Memory item id.", required=True),
                            "status": {
                                "type": "string",
                                "enum": PROMOTE_STATUS_ENUM,
                                "default": "verified",
                            },
                            "confidence": {
                                "type": "number",
                                "description": "Optional replacement confidence.",
                                "minimum": 0,
                                "maximum": 1,
                            },
                            "note": _string_schema("Optional promotion note."),
                        },
                        "required": ["item_id"],
                    },
                    handler=self.promote,
                ),
                ToolSpec(
                    name="memory_deprecate",
                    description="Mark a memory item as deprecated without deleting it.",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "item_id": _string_schema("Memory item id.", required=True),
                            "note": _string_schema("Reason this memory is no longer reliable."),
                        },
                        "required": ["item_id"],
                    },
                    handler=self.deprecate,
                ),
            ],
        )

    async def initialize(self, config: dict[str, Any] | None = None) -> None:
        cfg = config or {}
        raw_path = cfg.get("db_path") or cfg.get("path") or os.environ.get(
            "RESEARCH_MCP_MEMORY_DB"
        )
        self.db_path = Path(raw_path) if raw_path else Path(".research_mcp") / "memory.sqlite3"
        self.store = MemoryStore(self.db_path)
        self.store.initialize()

    def status(self) -> dict[str, Any]:
        return self._store().status()

    def record(
        self,
        title: str,
        content: str,
        item_type: str = "note",
        status: str = "draft",
        confidence: float = 0.5,
        source_type: str = "user",
        source_ref: str = "",
        project: str = "",
        software: str = "",
        problem_signature: str = "",
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self._store().record(
            title=title,
            content=content,
            item_type=item_type or "note",
            status=status or "draft",
            confidence=confidence,
            source_type=source_type or "user",
            source_ref=source_ref,
            project=project,
            software=software,
            problem_signature=problem_signature,
            tags=tags,
            metadata=metadata,
        )

    def search(
        self,
        query: str,
        limit: int = 10,
        item_type: str = "",
        status: str = "",
        software: str = "",
        project: str = "",
        include_deprecated: bool = False,
    ) -> dict[str, Any]:
        return self._store().search(
            query,
            limit=limit,
            item_type=item_type,
            status=status,
            software=software,
            project=project,
            include_deprecated=include_deprecated,
        )

    def get(self, item_id: str) -> dict[str, Any]:
        item = self._store().get(item_id)
        if item is None:
            return {"status": "not_found", "item_id": item_id}
        return item

    def export_context(
        self,
        query: str,
        limit: int = 5,
        software: str = "",
        project: str = "",
    ) -> dict[str, Any]:
        return self._store().export_context(
            query,
            limit=limit,
            software=software,
            project=project,
        )

    def record_simulation_run(
        self,
        software: str,
        task: str,
        status: str,
        parameter_values: dict[str, Any] | None = None,
        input_files: list[str] | None = None,
        output_files: list[str] | None = None,
        log_excerpt: str = "",
        error_signature: str = "",
        fix_item_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        return self._store().record_simulation_run(
            software=software,
            task=task,
            status=status,
            parameters=parameter_values,
            input_files=input_files,
            output_files=output_files,
            log_excerpt=log_excerpt,
            error_signature=error_signature,
            fix_item_ids=fix_item_ids,
        )

    def record_error_case(
        self,
        title: str,
        problem: str,
        fix: str,
        software: str = "",
        cause: str = "",
        project: str = "",
        source_ref: str = "",
        status: str = "draft",
        confidence: float = 0.5,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        content = "\n\n".join(
            part
            for part in [f"Problem: {problem}", f"Cause: {cause}" if cause else "", f"Fix: {fix}"]
            if part
        )
        return self._store().record(
            title=title,
            content=content,
            item_type="simulation_error",
            status=status or "draft",
            confidence=confidence,
            source_type="simulation" if software else "user",
            source_ref=source_ref,
            project=project,
            software=software,
            problem_signature=problem,
            tags=[*(tags or []), software, "error_case"],
            metadata={"problem": problem, "cause": cause, "fix": fix},
        )

    def record_literature_note(
        self,
        title: str,
        content: str,
        zotero_key: str = "",
        doi: str = "",
        project: str = "",
        status: str = "draft",
        confidence: float = 0.55,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        source_ref = zotero_key or doi
        return self._store().record(
            title=title,
            content=content,
            item_type="literature_note",
            status=status or "draft",
            confidence=confidence,
            source_type="zotero" if zotero_key else "literature",
            source_ref=source_ref,
            project=project,
            tags=tags,
            metadata={"zotero_key": zotero_key, "doi": doi},
        )

    def index_zotero_item(
        self,
        item: dict[str, Any],
        project: str = "",
        status: str = "draft",
        confidence: float = 0.55,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        data = item.get("data", item)
        title = str(data.get("title") or item.get("title") or "Untitled Zotero item").strip()
        zotero_key = str(data.get("key") or item.get("key") or "").strip()
        doi = str(data.get("DOI") or data.get("doi") or "").strip()
        url = str(data.get("url") or item.get("url") or "").strip()
        creators = self._zotero_creators(data.get("creators", []))
        abstract = str(data.get("abstractNote") or data.get("abstract") or "").strip()
        date = str(data.get("date") or "").strip()
        item_type = str(data.get("itemType") or "").strip()
        content_parts = [
            f"Title: {title}",
            f"Authors: {', '.join(creators)}" if creators else "",
            f"Date: {date}" if date else "",
            f"Item type: {item_type}" if item_type else "",
            f"DOI: {doi}" if doi else "",
            f"URL: {url}" if url else "",
            f"Abstract: {abstract}" if abstract else "",
        ]
        content = "\n".join(part for part in content_parts if part)
        item_tags = [*self._zotero_tags(data.get("tags", [])), *(tags or [])]
        return self._store().record(
            title=title,
            content=content or title,
            item_type="literature_note",
            status=status or "draft",
            confidence=confidence,
            source_type="zotero",
            source_ref=zotero_key or doi,
            project=project,
            tags=item_tags,
            metadata={
                "zotero_key": zotero_key,
                "doi": doi,
                "url": url,
                "date": date,
                "item_type": item_type,
                "creators": creators,
            },
        )

    def record_web_source(
        self,
        title: str,
        content: str,
        source_url: str,
        project: str = "",
        status: str = "draft",
        confidence: float = 0.3,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        return self._store().record(
            title=title,
            content=content,
            item_type="web_source",
            status=status or "draft",
            confidence=confidence,
            source_type="web",
            source_ref=source_url,
            project=project,
            tags=tags,
            metadata={"source_url": source_url},
        )

    def record_web_results(
        self,
        search_query: str,
        results: list[dict[str, Any]],
        project: str = "",
        status: str = "draft",
        confidence: float = 0.3,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        recorded: list[dict[str, Any]] = []
        for result in results[:25]:
            title = str(result.get("title") or "").strip() or "Untitled web result"
            url = str(result.get("url") or result.get("source_url") or "").strip()
            content = str(
                result.get("content") or result.get("snippet") or result.get("summary") or title
            ).strip() or title
            recorded.append(
                self._store().record(
                    title=title,
                    content=content,
                    item_type="web_source",
                    status=status or "draft",
                    confidence=confidence,
                    source_type="web",
                    source_ref=url,
                    project=project,
                    tags=[*(tags or []), "web_search"],
                    metadata={"source_url": url, "search_query": search_query, "raw": result},
                )
            )
        return {"search_query": search_query, "count": len(recorded), "items": recorded}

    def feedback(
        self,
        item_id: str,
        outcome: str,
        feedback_type: str = "usage",
        note: str = "",
        run_ref: str = "",
        delta_confidence: float | None = None,
    ) -> dict[str, Any]:
        return self._store().record_feedback(
            item_id,
            feedback_type=feedback_type,
            outcome=outcome,
            note=note,
            run_ref=run_ref,
            delta_confidence=delta_confidence,
        )

    def promote(
        self,
        item_id: str,
        status: str = "verified",
        confidence: float | None = None,
        note: str = "",
    ) -> dict[str, Any]:
        return self._store().update_status(
            item_id,
            status or "verified",
            confidence=confidence,
            note=note,
        )

    def deprecate(self, item_id: str, note: str = "") -> dict[str, Any]:
        return self._store().update_status(item_id, "deprecated", note=note)

    def _store(self) -> MemoryStore:
        if self.store is None:
            raise RuntimeError("Memory adapter has not been initialized")
        return self.store

    def _zotero_creators(self, creators: list[dict[str, Any]]) -> list[str]:
        names: list[str] = []
        for creator in creators:
            name = " ".join(
                part
                for part in [creator.get("firstName", ""), creator.get("lastName", "")]
                if part
            ).strip()
            if not name:
                name = str(creator.get("name") or "").strip()
            if name:
                names.append(name)
        return names

    def _zotero_tags(self, tags: list[dict[str, Any]]) -> list[str]:
        return [str(tag.get("tag") or "").strip() for tag in tags if tag.get("tag")]

    def _base_record_properties(self) -> dict[str, Any]:
        return {
            "title": _string_schema("Memory title.", required=True),
            "content": _string_schema("Memory content.", required=True),
            "item_type": {"type": "string", "enum": ITEM_TYPE_ENUM, "default": "note"},
            "status": {"type": "string", "enum": STATUS_ENUM, "default": "draft"},
            "confidence": {"type": "number", "default": 0.5, "minimum": 0, "maximum": 1},
            "source_type": _string_schema("Source type such as user, simulation, zotero, web."),
            "source_ref": _string_schema("Source reference, URL, DOI, or run id."),
            "project": _string_schema("Optional project name."),
            "software": _string_schema("Optional related software."),
            "problem_signature": _string_schema("Optional problem or error signature."),
            "tags": _tags_schema(),
            "metadata": {"type": "object", "description": "Optional structured metadata."},
        }

    def _search_properties(self) -> dict[str, Any]:
        return {
            "query": _string_schema("Retrieval query.", required=True),
            "limit": {
                "type": "integer",
                "description": "Maximum results.",
                "default": 10,
                "minimum": 1,
                "maximum": 50,
            },
            "item_type": {"type": "string", "enum": ITEM_TYPE_ENUM, "default": ""},
            "status": {"type": "string", "enum": STATUS_ENUM, "default": ""},
            "software": _string_schema("Optional software filter."),
            "project": _string_schema("Optional project filter."),
            "include_deprecated": {"type": "boolean", "default": False},
        }
