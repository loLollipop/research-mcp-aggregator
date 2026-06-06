"""OpenAlex academic search adapter."""

from __future__ import annotations

from typing import Any

import httpx

from research_mcp.adapters import (
    AdapterMeta,
    BaseAdapter,
    ToolSpec,
    register_adapter,
)

OPENALEX_API = "https://api.openalex.org"


@register_adapter
class OpenAlexAdapter(BaseAdapter):
    """Search OpenAlex for papers, authors, and institutions."""

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    def metadata(self) -> AdapterMeta:
        return AdapterMeta(
            name="openalex",
            description="Search OpenAlex - a free, open catalog of 250M+ scholarly works",
            tools=[
                ToolSpec(
                    name="openalex_search_works",
                    description="Search scholarly works on OpenAlex.",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search query"},
                            "limit": {
                                "type": "integer",
                                "description": "Max results (default 10)",
                                "default": 10,
                            },
                            "from_year": {"type": "integer", "description": "Filter: from year"},
                            "to_year": {"type": "integer", "description": "Filter: to year"},
                        },
                        "required": ["query"],
                    },
                    handler=self.search_works,
                ),
                ToolSpec(
                    name="openalex_get_work",
                    description="Get work details from OpenAlex by work ID or DOI.",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "work_id": {
                                "type": "string",
                                "description": "OpenAlex work ID, URL, or DOI",
                            },
                        },
                        "required": ["work_id"],
                    },
                    handler=self.get_work,
                ),
                ToolSpec(
                    name="openalex_get_author",
                    description="Get author profile from OpenAlex by author ID.",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "author_id": {
                                "type": "string",
                                "description": "OpenAlex author ID (e.g. 'A5023888391')",
                            },
                        },
                        "required": ["author_id"],
                    },
                    handler=self.get_author,
                ),
            ],
        )

    async def initialize(self, config: dict[str, Any] | None = None) -> None:
        email = (config or {}).get("email", "")
        params = {}
        if email:
            params["mailto"] = email
        self._client = httpx.AsyncClient(timeout=30.0, params=params)

    async def shutdown(self) -> None:
        if self._client:
            await self._client.aclose()

    async def search_works(
        self, query: str, limit: int = 10, from_year: int = 0, to_year: int = 0
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "search": query,
            "per_page": str(min(limit, 50)),
            "select": (
                "id,title,authorships,publication_year,cited_by_count,"
                "open_access,primary_location,doi,type"
            ),
        }
        if from_year:
            params["filter"] = f"from_publication_date:{from_year}-01-01"
        if to_year:
            filt = params.get("filter", "")
            sep = "," if filt else ""
            params["filter"] = f"{filt}{sep}to_publication_date:{to_year}-12-31"
        resp = await self._client.get(  # type: ignore[union-attr]
            f"{OPENALEX_API}/works", params=params
        )
        resp.raise_for_status()
        data = resp.json()
        return {"total": data.get("meta", {}).get("count", 0), "works": data.get("results", [])}

    async def get_work(self, work_id: str) -> dict[str, Any]:
        normalized = self._normalize_work_id(work_id)
        resp = await self._client.get(  # type: ignore[union-attr]
            f"{OPENALEX_API}/works/{normalized}"
        )
        resp.raise_for_status()
        return resp.json()

    async def get_author(self, author_id: str) -> dict[str, Any]:
        resp = await self._client.get(  # type: ignore[union-attr]
            f"{OPENALEX_API}/authors/{author_id}"
        )
        resp.raise_for_status()
        return resp.json()

    def _normalize_work_id(self, work_id: str) -> str:
        value = work_id.strip()
        if value.startswith("https://doi.org/"):
            return f"doi:{value.removeprefix('https://doi.org/')}"
        if value.startswith("http://doi.org/"):
            return f"doi:{value.removeprefix('http://doi.org/')}"
        if value.startswith("10."):
            return f"doi:{value}"
        if "/works/" in value:
            return value.rsplit("/", 1)[-1]
        return value
