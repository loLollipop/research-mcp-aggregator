"""Tests for adapter discovery and registration contracts."""

from __future__ import annotations

from typing import Any

import pytest

import research_mcp.adapters as adapter_registry
from research_mcp.adapters import AdapterMeta, BaseAdapter
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
