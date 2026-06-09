"""Tests for adapter discovery and registration contracts."""

from __future__ import annotations

from typing import Any

import pytest

import research_mcp.adapters as adapter_registry
from research_mcp.adapters import AdapterMeta, BaseAdapter, ToolSpec
from research_mcp.server import ResearchMCPServer


class NoInstantiateAdapter(BaseAdapter):
    adapter_name = "no_instantiate"

    def __init__(self) -> None:
        raise AssertionError("discovery should not instantiate adapters with adapter_name")

    def metadata(self) -> AdapterMeta:
        raise AssertionError("discovery should not read metadata for adapter_name classes")

    async def initialize(self, config: dict[str, Any] | None = None) -> None:
        pass


class CountedRuntimeAdapter(BaseAdapter):
    adapter_name = "counted_runtime"
    init_count = 0

    def __init__(self) -> None:
        type(self).init_count += 1

    def metadata(self) -> AdapterMeta:
        return AdapterMeta(
            name=self.adapter_name,
            description="Counts runtime construction.",
            tools=[],
        )

    async def initialize(self, config: dict[str, Any] | None = None) -> None:
        pass


class LegacyNamedAdapter(BaseAdapter):
    init_count = 0

    def __init__(self) -> None:
        type(self).init_count += 1

    def metadata(self) -> AdapterMeta:
        return AdapterMeta(name="legacy_named", description="Legacy adapter.", tools=[])

    async def initialize(self, config: dict[str, Any] | None = None) -> None:
        pass


class FirstDuplicateToolAdapter(BaseAdapter):
    adapter_name = "first_duplicate_tool"

    def metadata(self) -> AdapterMeta:
        return AdapterMeta(
            name=self.adapter_name,
            description="First duplicate tool adapter.",
            tools=[
                ToolSpec(
                    name="duplicate_beta_tool",
                    description="First duplicate beta tool.",
                    input_schema={"type": "object", "properties": {}},
                    handler=self.tool,
                )
            ],
        )

    async def initialize(self, config: dict[str, Any] | None = None) -> None:
        pass

    def tool(self) -> dict[str, str]:
        return {"source": "first"}


class SecondDuplicateToolAdapter(BaseAdapter):
    adapter_name = "second_duplicate_tool"

    def metadata(self) -> AdapterMeta:
        return AdapterMeta(
            name=self.adapter_name,
            description="Second duplicate tool adapter.",
            tools=[
                ToolSpec(
                    name="duplicate_beta_tool",
                    description="Second duplicate beta tool.",
                    input_schema={"type": "object", "properties": {}},
                    handler=self.tool,
                )
            ],
        )

    async def initialize(self, config: dict[str, Any] | None = None) -> None:
        pass

    def tool(self) -> dict[str, str]:
        return {"source": "second"}


def test_discover_adapters_uses_adapter_name_without_instantiation(monkeypatch):
    adapter_registry.discover_adapters()
    monkeypatch.setattr(adapter_registry, "_ADAPTERS", {})
    monkeypatch.setattr(adapter_registry, "_PENDING", [NoInstantiateAdapter])

    adapter_registry.discover_adapters()

    assert adapter_registry.get_adapter_classes() == {"no_instantiate": NoInstantiateAdapter}


@pytest.mark.asyncio
async def test_server_initializes_discovered_adapter_once(monkeypatch):
    adapter_registry.discover_adapters()
    CountedRuntimeAdapter.init_count = 0
    monkeypatch.setattr(adapter_registry, "_ADAPTERS", {})
    monkeypatch.setattr(adapter_registry, "_PENDING", [CountedRuntimeAdapter])
    server = ResearchMCPServer()

    await server.initialize({})
    try:
        assert CountedRuntimeAdapter.init_count == 1
        assert "counted_runtime" in server._adapters
    finally:
        await server.shutdown()


def test_discover_adapters_keeps_legacy_metadata_fallback(monkeypatch):
    adapter_registry.discover_adapters()
    LegacyNamedAdapter.init_count = 0
    monkeypatch.setattr(adapter_registry, "_ADAPTERS", {})
    monkeypatch.setattr(adapter_registry, "_PENDING", [LegacyNamedAdapter])

    adapter_registry.discover_adapters()

    assert LegacyNamedAdapter.init_count == 1
    assert adapter_registry.get_adapter_classes() == {"legacy_named": LegacyNamedAdapter}


@pytest.mark.asyncio
async def test_server_rejects_duplicate_tool_registration(monkeypatch):
    adapter_registry.discover_adapters()
    monkeypatch.setattr(
        adapter_registry,
        "_ADAPTERS",
        {
            "first_duplicate_tool": FirstDuplicateToolAdapter,
            "second_duplicate_tool": SecondDuplicateToolAdapter,
        },
    )
    monkeypatch.setattr(adapter_registry, "_PENDING", [])
    server = ResearchMCPServer()

    await server.initialize({})
    try:
        assert "first_duplicate_tool" in server._adapters
        assert "second_duplicate_tool" not in server._adapters
        assert set(server._tools) == {"duplicate_beta_tool"}
        _spec, adapter = server._tools["duplicate_beta_tool"]
        assert isinstance(adapter, FirstDuplicateToolAdapter)
    finally:
        await server.shutdown()
