"""ArXiv literature search adapter."""

from __future__ import annotations

from typing import Any

import httpx

from research_mcp.adapters import (
    AdapterMeta,
    BaseAdapter,
    ToolSpec,
    register_adapter,
)

ARXIV_API = "https://export.arxiv.org/api/query"


@register_adapter
class ArxivAdapter(BaseAdapter):
    """Search arXiv for scientific papers."""

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    def metadata(self) -> AdapterMeta:
        return AdapterMeta(
            name="arxiv",
            description="Search arXiv for scientific papers and preprints",
            tools=[
                ToolSpec(
                    name="arxiv_search",
                    description="Search arXiv and return paper metadata.",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Search query using arXiv query syntax",
                            },
                            "max_results": {
                                "type": "integer",
                                "description": "Maximum number of results (default 10, max 50)",
                                "default": 10,
                            },
                            "sort_by": {
                                "type": "string",
                                "enum": ["relevance", "lastUpdatedDate", "submittedDate"],
                                "description": "Sort order (default: relevance)",
                                "default": "relevance",
                            },
                        },
                        "required": ["query"],
                    },
                    handler=self.search,
                ),
                ToolSpec(
                    name="arxiv_get_paper",
                    description="Get detailed information about a specific arXiv paper by ID.",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "paper_id": {
                                "type": "string",
                                "description": "arXiv paper ID, e.g. 2301.07041",
                            },
                        },
                        "required": ["paper_id"],
                    },
                    handler=self.get_paper,
                ),
            ],
        )

    async def initialize(self, config: dict[str, Any] | None = None) -> None:
        self._client = httpx.AsyncClient(timeout=30.0)

    async def shutdown(self) -> None:
        if self._client:
            await self._client.aclose()

    async def _fetch(self, params: dict[str, str]) -> str:
        assert self._client is not None
        resp = await self._client.get(ARXIV_API, params=params)
        resp.raise_for_status()
        return resp.text

    def _parse_entries(self, xml_text: str) -> list[dict[str, Any]]:
        """Simple XML parsing for arXiv Atom feed entries."""
        import re

        entries = []
        for block in re.split(r"<entry>", xml_text)[1:]:
            entry: dict[str, Any] = {}
            # Extract fields
            for field_name, tag in [
                ("title", "title"),
                ("id", "id"),
                ("summary", "summary"),
                ("published", "published"),
                ("updated", "updated"),
            ]:
                m = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", block, re.DOTALL)
                entry[field_name] = m.group(1).strip() if m else ""
            # Authors
            entry["authors"] = re.findall(r"<name>(.*?)</name>", block)
            # Categories
            entry["categories"] = re.findall(r'category[^>]*term="([^"]*)"', block)
            # PDF link
            m = re.search(r'<link[^>]*title="pdf"[^>]*href="([^"]*)"', block)
            if not m:
                m = re.search(r'<link[^>]*href="([^"]*)"[^>]*title="pdf"', block)
            entry["pdf_url"] = m.group(1) if m else ""
            # Clean up arXiv ID
            entry["arxiv_id"] = (
                entry["id"].split("/abs/")[-1] if "/abs/" in entry["id"] else entry["id"]
            )
            entries.append(entry)
        return entries

    async def search(
        self, query: str, max_results: int = 10, sort_by: str = "relevance"
    ) -> dict[str, Any]:
        sort_map = {
            "relevance": "relevance",
            "lastUpdatedDate": "lastUpdatedDate",
            "submittedDate": "submittedDate",
        }
        params = {
            "search_query": query,
            "start": "0",
            "max_results": str(min(max_results, 50)),
            "sortBy": sort_map.get(sort_by, "relevance"),
            "sortOrder": "descending",
        }
        xml = await self._fetch(params)
        entries = self._parse_entries(xml)
        return {"count": len(entries), "papers": entries}

    async def get_paper(self, paper_id: str) -> dict[str, Any]:
        params = {"id_list": paper_id, "max_results": "1"}
        xml = await self._fetch(params)
        entries = self._parse_entries(xml)
        if not entries:
            return {"error": f"Paper not found: {paper_id}"}
        return entries[0]
