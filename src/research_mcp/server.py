"""
Research MCP Server - Main entry point.

Aggregates all adapters into a single MCP server.
"""

from __future__ import annotations

import asyncio
import copy
import inspect
import json
import logging
import sys
from typing import Any

from jsonschema import ValidationError
from jsonschema.validators import validator_for
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
                    inputSchema=self._strict_object_schema(spec.input_schema),
                )
                for spec, _ in self._tools.values()
            ]

        @self.server.call_tool()
        async def call_tool(name: str, arguments: dict[str, Any] | None) -> list[TextContent]:
            return await self._call_tool(name, arguments)

    async def _call_tool(self, name: str, arguments: dict[str, Any] | None) -> list[TextContent]:
        if name not in self._tools:
            return self._json_response(
                {
                    "status": "error",
                    "error_type": "unknown_tool",
                    "tool": name,
                    "message": "Unknown tool",
                }
            )

        spec, _adapter = self._tools[name]
        tool_arguments = {} if arguments is None else arguments
        try:
            self._validate_arguments(spec, tool_arguments)
            result = spec.handler(**tool_arguments)
            if inspect.isawaitable(result):
                result = await result
            return self._json_response(result)
        except ValidationError as exc:
            return self._json_response(
                {
                    "status": "validation_error",
                    "error_type": "invalid_arguments",
                    "tool": name,
                    "message": exc.message,
                    "path": list(exc.path),
                }
            )
        except Exception:
            logger.exception("Tool %s failed", name)
            return self._json_response(
                {
                    "status": "error",
                    "error_type": "handler_failed",
                    "tool": name,
                    "message": "Tool execution failed. Check server logs for details.",
                }
            )

    def _validate_arguments(self, spec: ToolSpec, arguments: dict[str, Any]) -> None:
        schema = self._strict_object_schema(spec.input_schema or {"type": "object"})
        validator_cls = validator_for(schema)
        validator_cls.check_schema(schema)
        validator = validator_cls(schema)
        validator.validate(arguments)

    def _strict_object_schema(self, schema: dict[str, Any]) -> dict[str, Any]:
        strict_schema = copy.deepcopy(schema)
        if strict_schema.get("type") == "object" and "additionalProperties" not in strict_schema:
            strict_schema["additionalProperties"] = False
        return strict_schema

    def _json_response(self, result: Any) -> list[TextContent]:
        text = (
            json.dumps(result, ensure_ascii=False, indent=2)
            if isinstance(result, (dict, list))
            else str(result)
        )
        return [TextContent(type="text", text=text)]

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
