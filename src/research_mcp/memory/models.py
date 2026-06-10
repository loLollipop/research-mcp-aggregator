"""Shared constants and helpers for the local memory store."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

VALID_STATUSES = {"draft", "verified", "approved", "deprecated", "failed"}
VALID_ITEM_TYPES = {
    "note",
    "preference",
    "workflow",
    "simulation_run",
    "simulation_error",
    "literature_note",
    "web_source",
}

STATUS_WEIGHTS = {
    "approved": 1.0,
    "verified": 0.85,
    "draft": 0.35,
    "failed": 0.1,
    "deprecated": -0.5,
}

SOURCE_WEIGHTS = {
    "simulation": 0.25,
    "user": 0.2,
    "zotero": 0.15,
    "official_doc": 0.15,
    "literature": 0.1,
    "web": -0.05,
}


def utc_now() -> str:
    """Return a stable UTC timestamp for persisted memory metadata."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def clamp_confidence(value: float | int | None, default: float = 0.5) -> float:
    """Normalize confidence into the inclusive [0, 1] interval."""
    try:
        numeric = float(default if value is None else value)
    except (TypeError, ValueError):
        numeric = default
    return max(0.0, min(1.0, numeric))


def normalize_status(status: str | None, default: str = "draft") -> str:
    normalized = (status or default).strip().lower()
    if normalized not in VALID_STATUSES:
        raise ValueError(f"Unsupported memory status: {status}")
    return normalized


def normalize_item_type(item_type: str | None, default: str = "note") -> str:
    normalized = (item_type or default).strip().lower()
    if normalized not in VALID_ITEM_TYPES:
        raise ValueError(f"Unsupported memory item type: {item_type}")
    return normalized


def normalize_tags(tags: list[str] | None) -> list[str]:
    seen: set[str] = set()
    normalized: list[str] = []
    for tag in tags or []:
        clean = str(tag).strip()
        key = clean.lower()
        if clean and key not in seen:
            seen.add(key)
            normalized.append(clean)
    return normalized


def dumps_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def loads_json(value: str | None, fallback: Any) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def query_terms(query: str) -> list[str]:
    """Extract simple search terms that are safe for LIKE and FTS fallback queries."""
    return [term.lower() for term in re.findall(r"[\w\-]+", query or "") if term.strip()]


def priority_score(item: dict[str, Any], match_score: float = 0.0) -> float:
    """Score a memory item for retrieval using trust, feedback, and textual match."""
    status = str(item.get("status") or "draft").lower()
    source_type = str(item.get("source_type") or "").lower()
    confidence = clamp_confidence(item.get("confidence"), default=0.5)
    success_count = int(item.get("success_count") or 0)
    failure_count = int(item.get("failure_count") or 0)

    score = match_score
    score += STATUS_WEIGHTS.get(status, 0.0)
    score += SOURCE_WEIGHTS.get(source_type, 0.0)
    score += confidence
    score += min(success_count, 5) * 0.08
    score -= min(failure_count, 5) * 0.12
    return round(score, 6)
