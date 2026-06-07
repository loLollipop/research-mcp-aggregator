"""Skipped-by-default live smoke tests for literature adapters."""

from __future__ import annotations

import os

import pytest

from research_mcp.adapters.arxiv_adapter import ArxivAdapter
from research_mcp.adapters.openalex_adapter import OpenAlexAdapter
from research_mcp.adapters.semantic_scholar_adapter import SemanticScholarAdapter
from research_mcp.adapters.zotero_adapter import ZoteroAdapter

pytestmark = pytest.mark.live


@pytest.mark.asyncio
async def test_live_arxiv_search_smoke() -> None:
    adapter = ArxivAdapter()
    await adapter.initialize({})
    try:
        result = await adapter.search("graph neural networks", max_results=1)
    finally:
        await adapter.shutdown()

    assert len(result["papers"]) <= 1
    assert "papers" in result


@pytest.mark.asyncio
async def test_live_openalex_search_smoke() -> None:
    adapter = OpenAlexAdapter()
    await adapter.initialize({})
    try:
        result = await adapter.search_works("graph neural networks", limit=1)
    finally:
        await adapter.shutdown()

    assert result["total"] >= 0
    assert len(result["works"]) <= 1


@pytest.mark.asyncio
async def test_live_semantic_scholar_search_smoke() -> None:
    adapter = SemanticScholarAdapter()
    await adapter.initialize({"api_key": os.environ.get("SEMANTIC_SCHOLAR_API_KEY", "")})
    try:
        result = await adapter.search("graph neural networks", limit=1)
    finally:
        await adapter.shutdown()

    assert result["total"] >= 0
    assert len(result["papers"]) <= 1


@pytest.mark.asyncio
async def test_live_zotero_search_smoke() -> None:
    required_env = ["ZOTERO_API_KEY", "ZOTERO_LIBRARY_ID", "ZOTERO_LIBRARY_TYPE"]
    if not all(os.environ.get(name) for name in required_env):
        pytest.skip("Zotero live smoke test requires Zotero environment variables")

    adapter = ZoteroAdapter()
    await adapter.initialize({})
    try:
        status = await adapter.status()
        result = await adapter.search_items("graph", limit=1)
    finally:
        await adapter.shutdown()

    assert status["configured"] is True
    assert result["count"] <= 1
    assert "items" in result
