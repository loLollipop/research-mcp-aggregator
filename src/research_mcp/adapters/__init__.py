"""
Adapter base class and registry for Research MCP.

Each domain (literature, code, writing, engineering) is an adapter
that registers its tools with the MCP server.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ToolSpec:
    """Specification for a single MCP tool."""

    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Callable[..., Any]


@dataclass
class AdapterMeta:
    """Metadata about an adapter."""

    name: str
    description: str
    tools: list[ToolSpec] = field(default_factory=list)


class BaseAdapter(ABC):
    """Base class for all research MCP adapters."""

    adapter_name: str | None = None

    @abstractmethod
    def metadata(self) -> AdapterMeta:
        """Return adapter metadata and tool list."""

    @abstractmethod
    async def initialize(self, config: dict[str, Any] | None = None) -> None:
        """Initialize the adapter (e.g., set up HTTP clients)."""

    async def shutdown(self) -> None:
        """Clean up resources."""


# ---------------------------------------------------------------------------
# Global adapter registry
# ---------------------------------------------------------------------------
_ADAPTERS: dict[str, type[BaseAdapter]] = {}
_PENDING: list[type[BaseAdapter]] = []


def register_adapter(cls: type[BaseAdapter]) -> type[BaseAdapter]:
    """Class decorator to register an adapter.

    Usage::

        @register_adapter
        class ArxivAdapter(BaseAdapter):
            ...
    """
    _PENDING.append(cls)
    return cls


def get_adapter_classes() -> dict[str, type[BaseAdapter]]:
    """Return all registered adapter classes."""
    return dict(_ADAPTERS)


def discover_adapters() -> None:
    """Import all adapter modules to trigger registration."""
    from research_mcp.adapters import (  # noqa: F401
        arxiv_adapter,
        docx_adapter,
        external_mcp_adapter,
        figure_adapter,
        latex_adapter,
        nature_adapter,
        openalex_adapter,
        pfc_docs_adapter,
        semantic_scholar_adapter,
        simulation_adapter,
        workflow_adapter,
        writing_adapter,
        zotero_adapter,
    )

    for cls in _PENDING:
        adapter_name = cls.adapter_name
        if adapter_name is None:
            instance = cls()
            adapter_name = instance.metadata().name
        _ADAPTERS[adapter_name] = cls
        logger.debug("Registered adapter: %s", adapter_name)
    _PENDING.clear()
