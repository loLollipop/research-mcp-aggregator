"""Tests for the SQLite-backed long-term memory store."""

from __future__ import annotations

from research_mcp.memory.store import MemoryStore


def _store(tmp_path):
    store = MemoryStore(tmp_path / "memory.sqlite3")
    store.initialize()
    return store


def test_memory_store_records_and_searches_ranked_items(tmp_path):
    store = _store(tmp_path)
    draft = store.record(
        title="PFC packing unstable",
        content="Unbalanced force remains high after ball distribute.",
        item_type="simulation_error",
        status="draft",
        confidence=0.3,
        source_type="web",
        software="PFC",
        tags=["PFC", "packing"],
    )
    approved = store.record(
        title="PFC packing fix",
        content="Increase porosity and apply calm cycles before wall compaction.",
        item_type="simulation_error",
        status="approved",
        confidence=0.9,
        source_type="simulation",
        software="PFC",
        tags=["PFC", "packing", "porosity"],
    )

    result = store.search("PFC packing porosity", software="PFC")

    assert result["count"] == 2
    assert result["results"][0]["id"] == approved["id"]
    assert {item["id"] for item in result["results"]} == {draft["id"], approved["id"]}


def test_memory_feedback_updates_confidence_and_counts(tmp_path):
    store = _store(tmp_path)
    item = store.record(title="COMSOL mesh fix", content="Use finer local mesh.")

    updated = store.record_feedback(item["id"], outcome="worked", note="Solved the run")

    assert updated["success_count"] == 1
    assert updated["failure_count"] == 0
    assert updated["confidence"] > item["confidence"]
    assert updated["feedback_events"][0]["outcome"] == "worked"


def test_memory_status_updates_and_deprecated_filter(tmp_path):
    store = _store(tmp_path)
    item = store.record(title="Old strategy", content="This strategy is no longer reliable.")

    deprecated = store.update_status(item["id"], "deprecated", note="Superseded")

    assert deprecated["status"] == "deprecated"
    assert store.search("strategy")["count"] == 0
    assert store.search("strategy", include_deprecated=True)["count"] == 1


def test_memory_records_simulation_run_as_memory_item(tmp_path):
    store = _store(tmp_path)

    result = store.record_simulation_run(
        software="PFC",
        task="biaxial packing",
        status="success",
        parameters={"porosity": 0.36},
        output_files=["outputs/history.csv"],
    )

    assert result["run_id"]
    memory_item = result["memory_item"]
    assert memory_item["item_type"] == "simulation_run"
    assert memory_item["status"] == "verified"
    assert memory_item["source_type"] == "simulation"
    assert memory_item["metadata"]["run_id"] == result["run_id"]
