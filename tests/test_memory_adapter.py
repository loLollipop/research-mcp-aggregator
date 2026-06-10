"""Tests for the long-term memory MCP adapter."""

from __future__ import annotations

from research_mcp.adapters.memory_adapter import MemoryAdapter
from research_mcp.server import ResearchMCPServer


async def test_memory_adapter_initializes_with_configured_db_path(tmp_path):
    adapter = MemoryAdapter()

    await adapter.initialize({"db_path": str(tmp_path / "memory.sqlite3")})

    status = adapter.status()
    assert status["status"] == "ok"
    assert status["item_count"] == 0


async def test_memory_adapter_records_searches_and_exports_context(tmp_path):
    adapter = MemoryAdapter()
    await adapter.initialize({"db_path": str(tmp_path / "memory.sqlite3")})

    item = adapter.record_error_case(
        title="PFC porosity fix",
        software="PFC",
        problem="Unbalanced force remains high",
        cause="Initial porosity too low",
        fix="Increase porosity and apply calm cycles",
        status="verified",
        confidence=0.8,
        tags=["packing"],
    )

    result = adapter.search("unbalanced porosity", software="PFC")
    context = adapter.export_context("unbalanced porosity", software="PFC")

    assert result["count"] == 1
    assert result["results"][0]["id"] == item["id"]
    assert "PFC porosity fix" in context["context"]


async def test_memory_adapter_indexes_zotero_item(tmp_path):
    adapter = MemoryAdapter()
    await adapter.initialize({"db_path": str(tmp_path / "memory.sqlite3")})

    item = adapter.index_zotero_item(
        {
            "data": {
                "key": "ABCD1234",
                "title": "DEM coupling timestep guideline",
                "DOI": "10.0000/example",
                "date": "2026",
                "itemType": "journalArticle",
                "abstractNote": "Use stable coupling timesteps for DEM-fluid coupling.",
                "creators": [{"firstName": "A.", "lastName": "Researcher"}],
                "tags": [{"tag": "DEM"}],
            }
        },
        tags=["coupling"],
    )

    assert item["item_type"] == "literature_note"
    assert item["source_type"] == "zotero"
    assert item["source_ref"] == "ABCD1234"
    assert item["metadata"]["doi"] == "10.0000/example"
    assert "DEM" in item["tags"]
    assert "coupling" in item["tags"]


async def test_memory_adapter_records_web_results_batch_as_drafts(tmp_path):
    adapter = MemoryAdapter()
    await adapter.initialize({"db_path": str(tmp_path / "memory.sqlite3")})

    result = adapter.record_web_results(
        search_query="COMSOL mesh narrow fracture",
        results=[
            {
                "title": "COMSOL mesh guide",
                "url": "https://example.test/comsol-mesh",
                "snippet": "Use local mesh refinement near narrow fractures.",
            }
        ],
        tags=["COMSOL", "mesh"],
    )

    assert result["count"] == 1
    item = result["items"][0]
    assert item["item_type"] == "web_source"
    assert item["status"] == "draft"
    assert item["confidence"] == 0.3
    assert item["source_ref"] == "https://example.test/comsol-mesh"
    assert item["metadata"]["search_query"] == "COMSOL mesh narrow fracture"


async def test_memory_adapter_registered_on_server(tmp_path):
    server = ResearchMCPServer()

    await server.initialize({"memory": {"db_path": str(tmp_path / "memory.sqlite3")}})
    try:
        assert "memory" in server._adapters
        assert "memory_search" in server._tools
        assert "memory_index_zotero_item" in server._tools
        assert "memory_record_web_results" in server._tools
        assert "memory_record_simulation_run" in server._tools
    finally:
        await server.shutdown()
