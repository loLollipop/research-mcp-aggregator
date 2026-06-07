"""Focused tests for literature adapter helper behavior."""

import httpx
import pytest

from research_mcp.adapters.arxiv_adapter import ArxivAdapter
from research_mcp.adapters.openalex_adapter import OpenAlexAdapter
from research_mcp.adapters.semantic_scholar_adapter import SemanticScholarAdapter
from research_mcp.adapters.zotero_adapter import ZoteroAdapter


class FakeArxivClient:
    def __init__(self) -> None:
        self.params = []

    async def get(self, url, params=None):
        self.params.append(params or {})
        return httpx.Response(
            200,
            text="<feed xmlns=\"http://www.w3.org/2005/Atom\"></feed>",
            request=httpx.Request("GET", url),
        )


@pytest.mark.asyncio
async def test_arxiv_search_clamps_result_limits():
    adapter = ArxivAdapter()
    client = FakeArxivClient()
    adapter._client = client

    await adapter.search("graph", max_results=0)
    await adapter.search("graph", max_results=500)

    assert client.params[0]["max_results"] == "1"
    assert client.params[1]["max_results"] == "50"


@pytest.mark.asyncio
async def test_semantic_scholar_initialize_uses_single_client_with_api_key():
    adapter = SemanticScholarAdapter()
    await adapter.initialize({"api_key": "demo-key"})
    try:
        assert adapter._client is not None
        assert adapter._client.headers["x-api-key"] == "demo-key"
    finally:
        await adapter.shutdown()


class FakeSemanticScholarClient:
    def __init__(self) -> None:
        self.calls = []

    async def get(self, url, params=None):
        self.calls.append((url, params or {}))
        if url.endswith("/citations"):
            payload = {"data": [{"citingPaper": {"paperId": "citing"}}]}
        elif url.endswith("/references"):
            payload = {"data": [{"citedPaper": {"paperId": "cited"}}]}
        elif url.endswith("/paper/search"):
            payload = {"total": 0, "data": []}
        else:
            payload = {"paperId": "paper"}
        return httpx.Response(200, json=payload, request=httpx.Request("GET", url))


@pytest.mark.asyncio
async def test_semantic_scholar_quotes_path_ids_and_clamps_limits():
    adapter = SemanticScholarAdapter()
    client = FakeSemanticScholarClient()
    adapter._client = client

    await adapter.search("graph", limit=0)
    await adapter.get_paper("DOI:10.1145/123/456")
    await adapter.get_citations("DOI:10.1145/123/456", limit=500)
    await adapter.get_references("DOI:10.1145/123/456", limit=-1)

    assert client.calls[0][1]["limit"] == "1"
    assert client.calls[1][0].endswith("/paper/DOI%3A10.1145%2F123%2F456")
    assert client.calls[2][0].endswith("/paper/DOI%3A10.1145%2F123%2F456/citations")
    assert client.calls[2][1]["limit"] == "50"
    assert client.calls[3][0].endswith("/paper/DOI%3A10.1145%2F123%2F456/references")
    assert client.calls[3][1]["limit"] == "1"


class FakeOpenAlexClient:
    def __init__(self) -> None:
        self.calls = []

    async def get(self, url, params=None):
        self.calls.append((url, params or {}))
        if url.endswith("/works"):
            payload = {"meta": {"count": 0}, "results": []}
        else:
            payload = {"id": url}
        return httpx.Response(200, json=payload, request=httpx.Request("GET", url))


@pytest.mark.asyncio
async def test_openalex_quotes_path_ids_and_clamps_limits():
    adapter = OpenAlexAdapter()
    client = FakeOpenAlexClient()
    adapter._client = client

    await adapter.search_works("graph", limit=0)
    await adapter.get_work("https://doi.org/10.1145/123/456")
    await adapter.get_author("A/123")

    assert client.calls[0][1]["per_page"] == "1"
    assert client.calls[1][0].endswith("/works/doi:10.1145%2F123%2F456")
    assert client.calls[2][0].endswith("/authors/A%2F123")


class FakeZoteroClient:
    def __init__(self) -> None:
        self.get_urls = []
        self.get_params = []
        self.put_urls = []
        self.updated_json = None
        self.updated_headers = None

    async def get(self, url, params=None):
        self.get_urls.append(url)
        self.get_params.append(params or {})
        if url.endswith("/items") or "/collections/" in url:
            return httpx.Response(200, json=[], request=httpx.Request("GET", url))
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
        self.put_urls.append(url)
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
        "ABC/123",
        add_tags=[" add ", ""],
        remove_tags=["remove", " "],
    )

    assert result["item_key"] == "ABC/123"
    assert result["tags"] == [{"tag": "add"}, {"tag": "keep"}]
    assert client.get_urls == ["https://api.zotero.org/users/1/items/ABC%2F123"]
    assert client.put_urls == ["https://api.zotero.org/users/1/items/ABC%2F123"]
    assert client.updated_json["tags"] == [{"tag": "add"}, {"tag": "keep"}]
    assert client.updated_headers == {"If-Unmodified-Since-Version": "7"}


@pytest.mark.asyncio
async def test_zotero_search_items_quotes_collection_key_and_clamps_limit():
    adapter = ZoteroAdapter()
    adapter.library_id = "1"
    adapter.base_path = "https://api.zotero.org/users/1"
    client = FakeZoteroClient()
    adapter._client = client

    await adapter.search_items("graph", limit=0, collection_key="COL/123")

    assert client.get_urls == ["https://api.zotero.org/users/1/collections/COL%2F123/items"]
    assert client.get_params == [
        {"q": "graph", "limit": "1", "format": "json", "include": "data"}
    ]
