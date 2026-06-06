"""Semantic Scholar literature search adapter."""

from __future__ import annotations

from typing import Any

import httpx

from research_mcp.adapters import (
    AdapterMeta,
    BaseAdapter,
    ToolSpec,
    register_adapter,
)

S2_API = "https://api.semanticscholar.org/graph/v1"


@register_adapter
class SemanticScholarAdapter(BaseAdapter):
    """Search Semantic Scholar for papers with citation data."""

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    def metadata(self) -> AdapterMeta:
        return AdapterMeta(
            name="semantic_scholar",
            description="Search Semantic Scholar for papers, authors, and citation networks",
            tools=[
                ToolSpec(
                    name="s2_search",
                    description="Search papers on Semantic Scholar.",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search query"},
                            "limit": {
                                "type": "integer",
                                "description": "Max results (default 10)",
                                "default": 10,
                            },
                            "year": {
                                "type": "string",
                                "description": "Year range filter, e.g. '2020-2024' or '2023-'",
                            },
                            "fields_of_study": {
                                "type": "string",
                                "description": "Comma-separated fields of study",
                            },
                        },
                        "required": ["query"],
                    },
                    handler=self.search,
                ),
                ToolSpec(
                    name="s2_get_paper",
                    description="Get detailed paper info by Semantic Scholar ID or DOI.",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "paper_id": {
                                "type": "string",
                                "description": "Paper ID (S2 ID, DOI, ArXiv ID, etc.)",
                            },
                        },
                        "required": ["paper_id"],
                    },
                    handler=self.get_paper,
                ),
                ToolSpec(
                    name="s2_get_citations",
                    description="Get papers that cite a given paper.",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "paper_id": {"type": "string", "description": "Paper ID"},
                            "limit": {
                                "type": "integer",
                                "description": "Max results (default 10)",
                                "default": 10,
                            },
                        },
                        "required": ["paper_id"],
                    },
                    handler=self.get_citations,
                ),
                ToolSpec(
                    name="s2_get_references",
                    description="Get papers referenced by a given paper.",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "paper_id": {"type": "string", "description": "Paper ID"},
                            "limit": {
                                "type": "integer",
                                "description": "Max results (default 10)",
                                "default": 10,
                            },
                        },
                        "required": ["paper_id"],
                    },
                    handler=self.get_references,
                ),
            ],
        )

    async def initialize(self, config: dict[str, Any] | None = None) -> None:
        api_key = (config or {}).get("api_key", "")
        headers = {}
        if api_key:
            headers["x-api-key"] = api_key
        self._client = httpx.AsyncClient(timeout=30.0, headers=headers)

    async def shutdown(self) -> None:
        if self._client:
            await self._client.aclose()

    FIELDS = (
        "paperId,externalIds,title,abstract,year,referenceCount,citationCount,"
        "authors,fieldsOfStudy,url,publicationDate"
    )

    async def search(
        self, query: str, limit: int = 10, year: str = "", fields_of_study: str = ""
    ) -> dict[str, Any]:
        params: dict[str, str] = {
            "query": query,
            "limit": str(min(limit, 50)),
            "fields": self.FIELDS,
        }
        if year:
            params["year"] = year
        if fields_of_study:
            params["fieldsOfStudy"] = fields_of_study
        resp = await self._client.get(  # type: ignore[union-attr]
            f"{S2_API}/paper/search", params=params
        )
        resp.raise_for_status()
        data = resp.json()
        return {"total": data.get("total", 0), "papers": data.get("data", [])}

    async def get_paper(self, paper_id: str) -> dict[str, Any]:
        resp = await self._client.get(  # type: ignore[union-attr]
            f"{S2_API}/paper/{paper_id}", params={"fields": self.FIELDS}
        )
        resp.raise_for_status()
        return resp.json()

    async def get_citations(self, paper_id: str, limit: int = 10) -> dict[str, Any]:
        params = {"fields": "paperId,title,year,authors", "limit": str(min(limit, 50))}
        resp = await self._client.get(  # type: ignore[union-attr]
            f"{S2_API}/paper/{paper_id}/citations", params=params
        )
        resp.raise_for_status()
        data = resp.json()
        return {
            "count": len(data.get("data", [])),
            "citations": [c.get("citingPaper", {}) for c in data.get("data", [])],
        }

    async def get_references(self, paper_id: str, limit: int = 10) -> dict[str, Any]:
        params = {"fields": "paperId,title,year,authors", "limit": str(min(limit, 50))}
        resp = await self._client.get(  # type: ignore[union-attr]
            f"{S2_API}/paper/{paper_id}/references", params=params
        )
        resp.raise_for_status()
        data = resp.json()
        return {
            "count": len(data.get("data", [])),
            "references": [r.get("citedPaper", {}) for r in data.get("data", [])],
        }
