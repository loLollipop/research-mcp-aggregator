"""Disabled compatibility module for the retired MCP bridge.

research-mcp is now self-contained. Runtime adapter discovery no longer imports
or registers bridge tools from this module family.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class RetiredServerConfig:
    """Retained only for older imports; no process is started."""

    name: str
    command: str = ""
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    cwd: str = ""
    enabled: bool = False


def parse_external_servers(config: dict[str, Any]) -> list[RetiredServerConfig]:
    """Return no servers because external bridge runtime is retired."""
    return []
