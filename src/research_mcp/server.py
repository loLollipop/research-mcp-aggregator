"""
Research MCP Server - Main entry point.

Aggregates all adapters into a single MCP server.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    TextContent,
    Tool,
)

from research_mcp.adapters import (
    BaseAdapter,
    ToolSpec,
    discover_adapters,
    get_adapter_classes,
)

logger = logging.getLogger("research-mcp")


class ResearchMCPServer:
    """Main MCP server that aggregates all research adapters."""

    def __init__(self) -> None:
        self.server = Server("research-mcp")
        self._adapters: dict[str, BaseAdapter] = {}
        self._tools: dict[str, tuple[ToolSpec, BaseAdapter]] = {}
        self._setup_handlers()

    def _setup_handlers(self) -> None:
        """Register MCP protocol handlers."""

        @self.server.list_tools()
        async def list_tools() -> list[Tool]:
            return [
                Tool(
                    name=spec.name,
                    description=spec.description,
                    inputSchema=spec.input_schema,
                )
                for spec, _ in self._tools.values()
            ]

        @self.server.call_tool()
        async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
            if name not in self._tools:
                return [TextContent(type="text", text=f"Unknown tool: {name}")]
            spec, adapter = self._tools[name]
            try:
                result = await spec.handler(**arguments)
                text = (
                    json.dumps(result, ensure_ascii=False, indent=2)
                    if isinstance(result, (dict, list))
                    else str(result)
                )
                return [TextContent(type="text", text=text)]
            except Exception as e:
                logger.exception("Tool %s failed", name)
                return [TextContent(type="text", text=f"Error: {type(e).__name__}: {e}")]

    async def initialize(self, config: dict[str, Any] | None = None) -> None:
        """Discover and initialize all adapters."""
        discover_adapters()
        adapter_classes = get_adapter_classes()
        logger.info("Found %d adapters: %s", len(adapter_classes), list(adapter_classes.keys()))

        for name, cls in adapter_classes.items():
            adapter = cls()
            adapter_config = (config or {}).get(name, {})
            try:
                await adapter.initialize(adapter_config)
                meta = adapter.metadata()
                self._adapters[name] = adapter
                for tool_spec in meta.tools:
                    self._tools[tool_spec.name] = (tool_spec, adapter)
                logger.info("Initialized adapter '%s' with %d tools", name, len(meta.tools))
            except Exception:
                logger.exception("Failed to initialize adapter '%s'", name)

        logger.info("Total tools registered: %d", len(self._tools))

    async def shutdown(self) -> None:
        """Shut down all adapters."""
        for adapter in self._adapters.values():
            try:
                await adapter.shutdown()
            except Exception:
                logger.exception("Error shutting down adapter")

    async def run(self) -> None:
        """Run the MCP server via stdio."""
        await self.initialize()
        try:
            async with stdio_server() as (read_stream, write_stream):
                await self.server.run(
                    read_stream, write_stream, self.server.create_initialization_options()
                )
        finally:
            await self.shutdown()


def main() -> None:
    """Entry point for the research-mcp CLI."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        stream=sys.stderr,
    )
    server = ResearchMCPServer()
    asyncio.run(server.run())


if __name__ == "__main__":
    main()
