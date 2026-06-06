"""Focused tests for literature adapter helper behavior."""

import httpx
import pytest

from research_mcp.adapters.semantic_scholar_adapter import SemanticScholarAdapter
from research_mcp.adapters.zotero_adapter import ZoteroAdapter


@pytest.mark.asyncio
async def test_semantic_scholar_initialize_uses_single_client_with_api_key():
    adapter = SemanticScholarAdapter()
    await adapter.initialize({"api_key": "demo-key"})
    try:
        assert adapter._client is not None
        assert adapter._client.headers["x-api-key"] == "demo-key"
    finally:
        await adapter.shutdown()


class FakeZoteroClient:
    def __init__(self) -> None:
        self.updated_json = None
        self.updated_headers = None

    async def get(self, url):
        return httpx.Response(
            200,
            json={
                "data": {
                    "key": "ABC123",
                    "version": 7,
                    "tags": [{"tag": "keep"}, {"tag": "remove"}],
                }
            },
            request=httpx.Request("GET", url),
        )

    async def put(self, url, json, headers):
        self.updated_json = json
        self.updated_headers = headers
        return httpx.Response(204, request=httpx.Request("PUT", url))


@pytest.mark.asyncio
async def test_zotero_update_item_tags_strips_empty_tags():
    adapter = ZoteroAdapter()
    adapter.library_id = "1"
    adapter.base_path = "https://api.zotero.org/users/1"
    client = FakeZoteroClient()
    adapter._client = client

    result = await adapter.update_item_tags(
        "ABC123",
        add_tags=[" add ", ""],
        remove_tags=["remove", " "],
    )

    assert result["tags"] == [{"tag": "add"}, {"tag": "keep"}]
    assert client.updated_json["tags"] == [{"tag": "add"}, {"tag": "keep"}]
    assert client.updated_headers == {"If-Unmodified-Since-Version": "7"}
