"""Local PFC documentation tools ported from upstream pfc-mcp resources."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from research_mcp.adapters import AdapterMeta, BaseAdapter, ToolSpec, register_adapter

PFC_DOCS_ROOT = Path(__file__).resolve().parents[3] / "vendors" / "external" / "pfc-mcp"
PFC_RESOURCES_ROOT = PFC_DOCS_ROOT / "src" / "pfc_mcp" / "knowledge" / "resources"
COMMAND_DOCS_ROOT = PFC_RESOURCES_ROOT / "command_docs"
PYTHON_API_DOCS_ROOT = PFC_RESOURCES_ROOT / "python_sdk_docs"
DEFAULT_VERSION = "7.0"


@register_adapter
class PFCDocsAdapter(BaseAdapter):
    """Browse and search vendored PFC command documentation locally."""

    def metadata(self) -> AdapterMeta:
        return AdapterMeta(
            name="pfc_docs",
            description="Local PFC command documentation tools from audited pfc-mcp resources",
            tools=[
                ToolSpec(
                    name="pfc_docs_status",
                    description="Check whether vendored PFC documentation resources are available.",
                    input_schema={"type": "object", "properties": {}},
                    handler=self.status,
                ),
                ToolSpec(
                    name="pfc_browse_commands",
                    description="Browse PFC command categories or one command document.",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "command": {
                                "type": "string",
                                "description": (
                                    "Empty for categories, category for commands, "
                                    "or full command path"
                                ),
                            },
                            "version": {
                                "type": "string",
                                "description": "PFC documentation version",
                                "default": DEFAULT_VERSION,
                            },
                        },
                    },
                    handler=self.browse_commands,
                ),
                ToolSpec(
                    name="pfc_query_command",
                    description="Search PFC command documentation by keyword.",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search keywords"},
                            "limit": {
                                "type": "integer",
                                "description": "Max matches",
                                "default": 10,
                            },
                            "version": {
                                "type": "string",
                                "description": "PFC documentation version",
                                "default": DEFAULT_VERSION,
                            },
                        },
                        "required": ["query"],
                    },
                    handler=self.query_command,
                ),
                ToolSpec(
                    name="pfc_browse_python_api",
                    description="Browse PFC Python SDK documentation by API path.",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "api": {
                                "type": "string",
                                "description": (
                                    "Empty for root, module path, function path, "
                                    "or object method path"
                                ),
                            },
                        },
                    },
                    handler=self.browse_python_api,
                ),
                ToolSpec(
                    name="pfc_query_python_api",
                    description="Search PFC Python SDK documentation by keyword.",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search keywords"},
                            "limit": {
                                "type": "integer",
                                "description": "Max matches",
                                "default": 10,
                            },
                        },
                        "required": ["query"],
                    },
                    handler=self.query_python_api,
                ),
            ],
        )

    async def initialize(self, config: dict[str, Any] | None = None) -> None:
        pass

    async def status(self) -> dict[str, Any]:
        return {
            "available": COMMAND_DOCS_ROOT.exists() and PYTHON_API_DOCS_ROOT.exists(),
            "command_docs_root": str(COMMAND_DOCS_ROOT),
            "python_api_docs_root": str(PYTHON_API_DOCS_ROOT),
            "source": "vendors/external/pfc-mcp",
            "runtime_bridge_required": False,
        }

    async def browse_commands(
        self, command: str = "", version: str = DEFAULT_VERSION
    ) -> dict[str, Any]:
        index = _load_index()
        categories = index.get("categories", {})
        normalized = command.strip().lower().replace("_", "-")
        if not normalized:
            return {
                "source": "pfc-mcp command_docs",
                "action": "browse_categories",
                "version": version,
                "count": len(categories),
                "categories": [
                    {
                        "name": name,
                        "description": data.get("description", ""),
                        "command_count": len(data.get("commands", [])),
                    }
                    for name, data in sorted(categories.items())
                ],
            }

        parts = normalized.split()
        category = parts[0]
        if category not in categories:
            return {
                "error": "category_not_found",
                "category": category,
                "available_categories": sorted(categories),
            }
        if len(parts) == 1:
            commands = categories[category].get("commands", [])
            return {
                "source": "pfc-mcp command_docs",
                "action": "browse_category",
                "category": category,
                "version": version,
                "count": len(commands),
                "commands": commands,
            }

        command_name = "-".join(parts[1:])
        doc = _load_command_doc(category, command_name, version)
        if doc is None:
            return {
                "error": "command_not_found",
                "category": category,
                "command": command_name,
                "available_commands": [
                    cmd.get("name") for cmd in categories[category].get("commands", [])
                ],
            }
        return {
            "source": "pfc-mcp command_docs",
            "action": "browse_command",
            "category": category,
            "command": command_name,
            "version": version,
            "doc": doc,
        }

    async def query_command(
        self, query: str, limit: int = 10, version: str = DEFAULT_VERSION
    ) -> dict[str, Any]:
        terms = [term.lower() for term in query.replace("-", " ").split() if term.strip()]
        matches: list[dict[str, Any]] = []
        for item in _all_command_summaries(version):
            haystack = " ".join(
                str(item.get(field, ""))
                for field in (
                    "category",
                    "name",
                    "syntax",
                    "short_description",
                    "python_alternative",
                )
            ).lower()
            score = sum(1 for term in terms if term in haystack)
            if score:
                matches.append({**item, "score": score})
        matches.sort(key=lambda item: (-item["score"], item["category"], item["name"]))
        return {
            "source": "pfc-mcp command_docs",
            "action": "query_command",
            "query": query,
            "version": version,
            "count": min(len(matches), limit),
            "matches": matches[: max(1, min(limit, 50))],
        }

    async def browse_python_api(self, api: str = "") -> dict[str, Any]:
        index = _load_api_index()
        modules = index.get("modules", {})
        objects = index.get("objects", {})
        normalized = api.strip()
        if not normalized:
            return {
                "source": "pfc-mcp python_sdk_docs",
                "action": "browse_root",
                "module_count": len(modules),
                "object_count": len(objects),
                "modules": [
                    {
                        "path": _format_api_module_path(name),
                        "description": data.get("description", ""),
                        "function_count": len(data.get("functions", [])),
                    }
                    for name, data in sorted(modules.items())
                ],
                "objects": [
                    {
                        "name": name,
                        "description": data.get("description", ""),
                        "types": data.get("types", []),
                    }
                    for name, data in sorted(objects.items())
                ],
            }

        if not normalized.startswith("itasca"):
            return {"error": "api_path_must_start_with_itasca", "api": normalized}
        doc = _load_api_doc(normalized)
        if doc is not None:
            return {
                "source": "pfc-mcp python_sdk_docs",
                "action": "browse_api",
                "api": normalized,
                "doc": doc,
            }
        module_key = _api_path_to_module_key(normalized)
        module = _load_api_module(module_key)
        if module is not None:
            return {
                "source": "pfc-mcp python_sdk_docs",
                "action": "browse_module",
                "api": normalized,
                "module": module,
            }
        return {
            "error": "api_not_found",
            "api": normalized,
            "hints": [
                "Try pfc_query_python_api with keywords such as ball create or contact force."
            ],
        }

    async def query_python_api(self, query: str, limit: int = 10) -> dict[str, Any]:
        terms = [term.lower() for term in query.replace(".", " ").replace("_", " ").split() if term]
        matches: list[dict[str, Any]] = []
        for item in _all_api_summaries():
            haystack = " ".join(
                str(item.get(field, ""))
                for field in ("api_path", "signature", "description", "category")
            ).lower()
            score = sum(1 for term in terms if term in haystack)
            if score:
                matches.append({**item, "score": score})
        matches.sort(key=lambda item: (-item["score"], item["api_path"]))
        return {
            "source": "pfc-mcp python_sdk_docs",
            "action": "query_python_api",
            "query": query,
            "count": min(len(matches), limit),
            "matches": matches[: max(1, min(limit, 50))],
        }


@lru_cache(maxsize=1)
def _load_index() -> dict[str, Any]:
    index_path = COMMAND_DOCS_ROOT / "index.json"
    if not index_path.exists():
        raise FileNotFoundError(f"PFC command docs are not vendored: {index_path}")
    return json.loads(index_path.read_text(encoding="utf-8"))


@lru_cache(maxsize=512)
def _load_doc_file(relative_path: str) -> dict[str, Any] | None:
    path = COMMAND_DOCS_ROOT / relative_path
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _load_command_doc(category: str, command_name: str, version: str) -> dict[str, Any] | None:
    category_data = _load_index().get("categories", {}).get(category)
    if not category_data:
        return None
    command_file = None
    for command in category_data.get("commands", []):
        if command.get("name") == command_name:
            command_file = command.get("file")
            break
    if not command_file:
        return None
    raw = _load_doc_file(command_file)
    if raw is None:
        return None
    return _resolve_versioned_doc(raw, version)


def _resolve_versioned_doc(doc: dict[str, Any], version: str) -> dict[str, Any]:
    versions = doc.get("versions")
    if not isinstance(versions, dict):
        return doc
    if version not in versions:
        return {**doc, "available": False, "requested_version": version}
    resolved = {key: value for key, value in doc.items() if key != "versions"}
    resolved["versions"] = list(versions)
    version_doc = versions[version]
    if isinstance(version_doc, dict):
        resolved.update(version_doc)
    return resolved


@lru_cache(maxsize=8)
def _all_command_summaries(version: str) -> tuple[dict[str, Any], ...]:
    items: list[dict[str, Any]] = []
    categories = _load_index().get("categories", {})
    for category, category_data in categories.items():
        for command in category_data.get("commands", []):
            doc = _load_command_doc(category, command.get("name", ""), version) or {}
            if doc.get("available") is False:
                continue
            items.append(
                {
                    "category": category,
                    "name": command.get("name", ""),
                    "syntax": doc.get("syntax") or command.get("syntax", ""),
                    "short_description": command.get("short_description", ""),
                    "python_available": bool(command.get("python_available", False)),
                    "python_alternative": command.get("python_alternative", ""),
                }
            )
    return tuple(items)


def _format_api_module_path(module_key: str) -> str:
    return "itasca" if module_key == "itasca" else f"itasca.{module_key}"


def _api_path_to_module_key(api_path: str) -> str:
    return api_path.removeprefix("itasca.") if api_path != "itasca" else "itasca"


@lru_cache(maxsize=1)
def _load_api_index() -> dict[str, Any]:
    index_path = PYTHON_API_DOCS_ROOT / "index.json"
    if not index_path.exists():
        raise FileNotFoundError(f"PFC Python API docs are not vendored: {index_path}")
    return json.loads(index_path.read_text(encoding="utf-8"))


@lru_cache(maxsize=256)
def _load_api_json(relative_path: str) -> dict[str, Any] | None:
    path = PYTHON_API_DOCS_ROOT / relative_path
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _load_api_module(module_key: str) -> dict[str, Any] | None:
    module_info = _load_api_index().get("modules", {}).get(module_key)
    if not module_info:
        return None
    return _load_api_json(module_info.get("file", ""))


def _load_api_doc(api_path: str) -> dict[str, Any] | None:
    index = _load_api_index()
    ref = index.get("quick_ref", {}).get(api_path)
    if not ref:
        return None
    file_name, _, anchor = ref.partition("#")
    data = _load_api_json(file_name)
    if data is None:
        return None
    for section in ("functions", "methods"):
        for item in data.get(section, []):
            if item.get("name") == anchor:
                return item
    return None


@lru_cache(maxsize=1)
def _all_api_summaries() -> tuple[dict[str, Any], ...]:
    index = _load_api_index()
    summaries: list[dict[str, Any]] = []
    for module_key, module_info in index.get("modules", {}).items():
        module_doc = _load_api_module(module_key) or {}
        for func in module_doc.get("functions", []):
            api_path = f"{_format_api_module_path(module_key)}.{func.get('name', '')}"
            summaries.append(
                {
                    "api_path": api_path,
                    "category": module_key,
                    "signature": func.get("signature", ""),
                    "description": func.get("description", ""),
                }
            )
    for api_path, ref in index.get("quick_ref", {}).items():
        doc = _load_api_doc(api_path)
        if not doc:
            continue
        summaries.append(
            {
                "api_path": api_path,
                "category": ref.split("/", 2)[1] if "/" in ref else "object",
                "signature": doc.get("signature", ""),
                "description": doc.get("description", ""),
            }
        )
    return tuple({item["api_path"]: item for item in summaries}.values())
