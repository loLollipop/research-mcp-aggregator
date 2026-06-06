"""Shared utilities for research MCP adapters."""

from __future__ import annotations

from typing import Any

import httpx


async def http_get(
    url: str,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 30.0,
) -> dict[str, Any]:
    """Convenience async GET request returning JSON."""
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.get(url, params=params, headers=headers)
        resp.raise_for_status()
        return resp.json()


async def http_post(
    url: str,
    json: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 30.0,
) -> dict[str, Any]:
    """Convenience async POST request returning JSON."""
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(url, json=json, headers=headers)
        resp.raise_for_status()
        return resp.json()


def truncate(text: str, max_len: int = 500) -> str:
    """Truncate text with ellipsis."""
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def format_authors(authors: list[str]) -> str:
    """Format author list for display."""
    if len(authors) <= 3:
        return ", ".join(authors)
    return f"{authors[0]} et al. ({len(authors)} authors)"
