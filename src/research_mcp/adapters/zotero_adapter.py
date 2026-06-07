"""Zotero literature-management adapter.

Uses the Zotero Web API so searched literature can be saved into a library.
"""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import quote

import httpx

from research_mcp.adapters import AdapterMeta, BaseAdapter, ToolSpec, register_adapter

ZOTERO_API = "https://api.zotero.org"


@register_adapter
class ZoteroAdapter(BaseAdapter):
    """Search and write Zotero library items through the Zotero Web API."""

    adapter_name = "zotero"

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None
        self.library_type = "user"
        self.library_id = ""
        self.base_path = ""

    def metadata(self) -> AdapterMeta:
        return AdapterMeta(
            name="zotero",
            description="Zotero literature management through the Web API",
            tools=[
                ToolSpec(
                    name="zotero_status",
                    description="Check Zotero Web API configuration.",
                    input_schema={"type": "object", "properties": {}},
                    handler=self.status,
                ),
                ToolSpec(
                    name="zotero_search_items",
                    description="Search Zotero library items.",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Search query",
                                "minLength": 1,
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Max results",
                                "default": 10,
                                "minimum": 1,
                                "maximum": 50,
                            },
                            "collection_key": {
                                "type": "string",
                                "description": "Optional collection key",
                            },
                        },
                        "required": ["query"],
                    },
                    handler=self.search_items,
                ),
                ToolSpec(
                    name="zotero_get_item",
                    description="Get one Zotero item by key.",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "item_key": {
                                "type": "string",
                                "description": "Zotero item key",
                                "minLength": 1,
                            },
                        },
                        "required": ["item_key"],
                    },
                    handler=self.get_item,
                ),
                ToolSpec(
                    name="zotero_create_collection",
                    description="Create a Zotero collection and return its key.",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "Collection name",
                                "minLength": 1,
                            }
                        },
                        "required": ["name"],
                    },
                    handler=self.create_collection,
                ),
                ToolSpec(
                    name="zotero_add_by_doi",
                    description="Add a paper to Zotero from DOI using Zotero translate endpoint.",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "doi": {
                                "type": "string",
                                "description": "Paper DOI",
                                "minLength": 1,
                            },
                            "collection_key": {
                                "type": "string",
                                "description": "Optional collection key",
                            },
                            "tags": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Optional tags",
                            },
                        },
                        "required": ["doi"],
                    },
                    handler=self.add_by_doi,
                ),
                ToolSpec(
                    name="zotero_update_item_tags",
                    description="Add and/or remove tags on an existing Zotero item.",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "item_key": {
                                "type": "string",
                                "description": "Zotero item key",
                                "minLength": 1,
                            },
                            "add_tags": {"type": "array", "items": {"type": "string"}},
                            "remove_tags": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": ["item_key"],
                    },
                    handler=self.update_item_tags,
                ),
            ],
        )

    async def initialize(self, config: dict[str, Any] | None = None) -> None:
        cfg = config or {}
        api_key = cfg.get("api_key") or os.environ.get("ZOTERO_API_KEY", "")
        self.library_id = cfg.get("library_id") or os.environ.get("ZOTERO_LIBRARY_ID", "")
        self.library_type = cfg.get("library_type") or os.environ.get("ZOTERO_LIBRARY_TYPE", "user")
        headers = {"Accept": "application/json"}
        if api_key:
            headers["Zotero-API-Key"] = api_key
        self._client = httpx.AsyncClient(timeout=30.0, headers=headers)
        lib_segment = "users" if self.library_type == "user" else "groups"
        self.base_path = f"{ZOTERO_API}/{lib_segment}/{self.library_id}"

    async def shutdown(self) -> None:
        if self._client:
            await self._client.aclose()

    async def status(self) -> dict[str, Any]:
        return {
            "configured": bool(self.library_id and self._client),
            "library_type": self.library_type,
            "library_id": self.library_id,
            "needs": ["ZOTERO_API_KEY", "ZOTERO_LIBRARY_ID", "ZOTERO_LIBRARY_TYPE"],
        }

    async def search_items(
        self, query: str, limit: int = 10, collection_key: str = ""
    ) -> dict[str, Any]:
        self._require_config()
        params = {
            "q": query,
            "limit": str(max(1, min(limit, 50))),
            "format": "json",
            "include": "data",
        }
        path = f"{self.base_path}/items"
        if collection_key:
            encoded_collection = quote(collection_key, safe="")
            path = f"{self.base_path}/collections/{encoded_collection}/items"
        resp = await self._client.get(path, params=params)  # type: ignore[union-attr]
        resp.raise_for_status()
        items = resp.json()
        return {"count": len(items), "items": [self._summarize_item(i) for i in items]}

    async def get_item(self, item_key: str) -> dict[str, Any]:
        self._require_config()
        encoded_key = quote(item_key, safe="")
        resp = await self._client.get(  # type: ignore[union-attr]
            f"{self.base_path}/items/{encoded_key}",
            params={"format": "json", "include": "data"},
        )
        resp.raise_for_status()
        return resp.json()

    async def create_collection(self, name: str) -> dict[str, Any]:
        self._require_config()
        payload = [{"name": name}]
        resp = await self._client.post(  # type: ignore[union-attr]
            f"{self.base_path}/collections", json=payload
        )
        resp.raise_for_status()
        return resp.json()

    async def add_by_doi(
        self,
        doi: str,
        collection_key: str = "",
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        self._require_config()
        translate_payload = [{"itemType": "journalArticle", "DOI": doi}]
        if collection_key:
            translate_payload[0]["collections"] = [collection_key]
        if tags:
            translate_payload[0]["tags"] = [{"tag": tag} for tag in tags]
        resp = await self._client.post(  # type: ignore[union-attr]
            f"{self.base_path}/items", json=translate_payload
        )
        resp.raise_for_status()
        return resp.json()

    async def update_item_tags(
        self,
        item_key: str,
        add_tags: list[str] | None = None,
        remove_tags: list[str] | None = None,
    ) -> dict[str, Any]:
        self._require_config()
        encoded_key = quote(item_key, safe="")
        item_resp = await self._client.get(  # type: ignore[union-attr]
            f"{self.base_path}/items/{encoded_key}"
        )
        item_resp.raise_for_status()
        item = item_resp.json()
        data = item.get("data", item)
        existing = {tag.get("tag", "") for tag in data.get("tags", []) if tag.get("tag")}
        additions = {tag.strip() for tag in add_tags or [] if tag.strip()}
        removals = {tag.strip() for tag in remove_tags or [] if tag.strip()}
        updated = (existing | additions) - removals
        data["tags"] = [{"tag": tag} for tag in sorted(updated)]
        version = str(data.get("version") or item.get("version") or "")
        headers = {"If-Unmodified-Since-Version": version} if version else {}
        resp = await self._client.put(
            f"{self.base_path}/items/{encoded_key}", json=data, headers=headers
        )  # type: ignore[union-attr]
        resp.raise_for_status()
        return {
            "item_key": item_key,
            "tags": data["tags"],
            "response": resp.json() if resp.content else {},
        }

    def _require_config(self) -> None:
        if not self.library_id:
            raise RuntimeError(
                "Zotero is not configured. Set ZOTERO_LIBRARY_ID and ZOTERO_API_KEY."
            )

    def _summarize_item(self, item: dict[str, Any]) -> dict[str, Any]:
        data = item.get("data", {})
        creators = data.get("creators", [])
        authors = [
            " ".join(filter(None, [c.get("firstName", ""), c.get("lastName", "")])).strip()
            for c in creators
        ]
        return {
            "key": data.get("key", item.get("key", "")),
            "title": data.get("title", ""),
            "itemType": data.get("itemType", ""),
            "date": data.get("date", ""),
            "doi": data.get("DOI", ""),
            "authors": authors,
            "url": data.get("url", ""),
        }
