"""
Research MCP - An all-in-one MCP server for scientific research.

Aggregates literature search, code management, writing tools,
and engineering utilities into a single MCP server.
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("research-mcp")
except PackageNotFoundError:
    __version__ = "0+unknown"
