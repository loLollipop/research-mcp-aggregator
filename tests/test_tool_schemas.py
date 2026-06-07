"""Registry-wide MCP tool schema contract tests."""

from __future__ import annotations

import inspect
from collections import Counter
from typing import Any

import pytest
from jsonschema.validators import validator_for

from research_mcp.adapters import ToolSpec
from research_mcp.server import ResearchMCPServer


def _all_tool_specs(server: ResearchMCPServer) -> list[ToolSpec]:
    specs: list[ToolSpec] = []
    for adapter in server._adapters.values():
        specs.extend(adapter.metadata().tools)
    return specs


def _integer_property_schemas(server: ResearchMCPServer) -> list[tuple[str, str, dict[str, Any]]]:
    schemas: list[tuple[str, str, dict[str, Any]]] = []
    for spec in _all_tool_specs(server):
        for property_name, property_schema in spec.input_schema.get("properties", {}).items():
            if property_schema.get("type") == "integer":
                schemas.append((spec.name, property_name, property_schema))
    return schemas


def _property_schemas(server: ResearchMCPServer) -> list[tuple[str, str, dict[str, Any], bool]]:
    schemas: list[tuple[str, str, dict[str, Any], bool]] = []
    for spec in _all_tool_specs(server):
        required = set(spec.input_schema.get("required", []))
        for property_name, property_schema in spec.input_schema.get("properties", {}).items():
            schemas.append((spec.name, property_name, property_schema, property_name in required))
    return schemas


@pytest.mark.asyncio
async def test_registered_tool_names_are_unique_and_public():
    server = ResearchMCPServer()
    await server.initialize({})
    try:
        tool_names = [spec.name for spec in _all_tool_specs(server)]
        counts = Counter(tool_names)
        duplicates = sorted(name for name, count in counts.items() if count > 1)

        assert duplicates == []
        assert not any("__" in name for name in tool_names)
        assert set(server._tools) == set(tool_names)
    finally:
        await server.shutdown()


@pytest.mark.asyncio
async def test_all_tool_input_schemas_are_valid_object_schemas():
    server = ResearchMCPServer()
    await server.initialize({})
    try:
        for spec in _all_tool_specs(server):
            schema = spec.input_schema

            assert schema.get("type") == "object", spec.name
            assert isinstance(schema.get("properties"), dict), spec.name

            required = schema.get("required", [])
            assert isinstance(required, list), spec.name
            assert set(required) <= set(schema["properties"]), spec.name

            strict_schema = server._strict_object_schema(schema)
            validator_cls = validator_for(strict_schema)
            validator_cls.check_schema(strict_schema)
    finally:
        await server.shutdown()


@pytest.mark.asyncio
async def test_required_handler_parameters_are_schema_required():
    server = ResearchMCPServer()
    await server.initialize({})
    try:
        for spec in _all_tool_specs(server):
            schema_required = set(spec.input_schema.get("required", []))
            signature = inspect.signature(spec.handler)
            handler_required = {
                name
                for name, param in signature.parameters.items()
                if param.default is inspect.Parameter.empty
                and param.kind
                in (
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    inspect.Parameter.KEYWORD_ONLY,
                )
            }

            assert handler_required <= schema_required, spec.name
    finally:
        await server.shutdown()


@pytest.mark.asyncio
async def test_no_arg_tools_reject_unknown_arguments_at_validation_boundary():
    server = ResearchMCPServer()
    await server.initialize({})
    try:
        no_arg_specs = [
            spec
            for spec in _all_tool_specs(server)
            if not spec.input_schema.get("properties")
        ]

        assert no_arg_specs
        for spec in no_arg_specs:
            with pytest.raises(Exception, match="Additional properties"):
                server._validate_arguments(spec, {"unexpected": "value"})
    finally:
        await server.shutdown()


@pytest.mark.asyncio
async def test_common_integer_controls_have_lower_bounds():
    server = ResearchMCPServer()
    await server.initialize({})
    try:
        bounded_names = {
            "limit",
            "max_results",
            "timeout_seconds",
            "port",
            "processors",
            "processor_count",
            "preview_chars",
            "skip_newest",
        }
        missing = [
            f"{tool_name}.{property_name}"
            for tool_name, property_name, property_schema in _integer_property_schemas(server)
            if property_name in bounded_names and "minimum" not in property_schema
        ]

        assert missing == []
    finally:
        await server.shutdown()


@pytest.mark.asyncio
async def test_search_result_limits_have_upper_bounds():
    server = ResearchMCPServer()
    await server.initialize({})
    try:
        missing = [
            f"{tool_name}.{property_name}"
            for tool_name, property_name, property_schema in _integer_property_schemas(server)
            if property_name in {"limit", "max_results"}
            and tool_name not in {"pfc_check_task_status", "pfc_list_tasks"}
            and "maximum" not in property_schema
        ]

        assert missing == []
    finally:
        await server.shutdown()


@pytest.mark.asyncio
async def test_required_string_fields_reject_empty_values():
    server = ResearchMCPServer()
    await server.initialize({})
    try:
        missing = [
            f"{tool_name}.{property_name}"
            for tool_name, property_name, property_schema, is_required in _property_schemas(server)
            if is_required
            and property_schema.get("type") == "string"
            and "minLength" not in property_schema
        ]

        assert missing == []
    finally:
        await server.shutdown()


@pytest.mark.asyncio
async def test_required_array_fields_reject_empty_values():
    server = ResearchMCPServer()
    await server.initialize({})
    try:
        missing = [
            f"{tool_name}.{property_name}"
            for tool_name, property_name, property_schema, is_required in _property_schemas(server)
            if is_required
            and property_schema.get("type") == "array"
            and "minItems" not in property_schema
        ]

        assert missing == []
    finally:
        await server.shutdown()


@pytest.mark.asyncio
async def test_object_array_items_declare_required_fields():
    server = ResearchMCPServer()
    await server.initialize({})
    try:
        missing = [
            f"{tool_name}.{property_name}"
            for tool_name, property_name, property_schema, _is_required in _property_schemas(server)
            if property_schema.get("type") == "array"
            and property_schema.get("items", {}).get("type") == "object"
            and not property_schema.get("items", {}).get("required")
        ]

        assert missing == []
    finally:
        await server.shutdown()
