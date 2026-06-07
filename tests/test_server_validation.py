"""Tests for MCP server tool-call validation."""

from __future__ import annotations

import json
from typing import Any

import pytest

from research_mcp.adapters import ToolSpec
from research_mcp.server import ResearchMCPServer


def _decode_response(text_content: Any) -> dict[str, Any]:
    return json.loads(text_content[0].text)


@pytest.mark.asyncio
async def test_call_tool_returns_validation_error_for_invalid_arguments():
    server = ResearchMCPServer()

    def handler(required: str) -> dict[str, str]:
        return {"required": required}

    spec = ToolSpec(
        name="needs_required",
        description="Needs a required string.",
        input_schema={
            "type": "object",
            "properties": {"required": {"type": "string"}},
            "required": ["required"],
        },
        handler=handler,
    )
    server._tools[spec.name] = (spec, object())  # type: ignore[arg-type]

    response = _decode_response(await server._call_tool("needs_required", {}))

    assert response["status"] == "validation_error"
    assert response["error_type"] == "invalid_arguments"
    assert response["tool"] == "needs_required"
    assert "required" in response["message"]


@pytest.mark.asyncio
async def test_call_tool_sanitizes_handler_errors():
    server = ResearchMCPServer()

    def handler() -> dict[str, str]:
        raise RuntimeError("secret path C:/Users/test/.env token=abc")

    spec = ToolSpec(
        name="raises",
        description="Raises an exception.",
        input_schema={"type": "object"},
        handler=handler,
    )
    server._tools[spec.name] = (spec, object())  # type: ignore[arg-type]

    response = _decode_response(await server._call_tool("raises", {}))

    assert response == {
        "status": "error",
        "error_type": "handler_failed",
        "tool": "raises",
        "message": "Tool execution failed. Check server logs for details.",
    }


@pytest.mark.asyncio
async def test_call_tool_rejects_unknown_arguments():
    server = ResearchMCPServer()

    def handler() -> dict[str, str]:
        return {"status": "ok"}

    spec = ToolSpec(
        name="no_unknown_args",
        description="Rejects unknown arguments.",
        input_schema={"type": "object", "properties": {}},
        handler=handler,
    )
    server._tools[spec.name] = (spec, object())  # type: ignore[arg-type]

    response = _decode_response(await server._call_tool("no_unknown_args", {"unexpected": 1}))

    assert response["status"] == "validation_error"
    assert response["error_type"] == "invalid_arguments"
    assert response["tool"] == "no_unknown_args"
    assert "Additional properties" in response["message"]


@pytest.mark.asyncio
async def test_call_tool_accepts_none_arguments_for_no_arg_tools():
    server = ResearchMCPServer()

    def handler() -> dict[str, str]:
        return {"status": "ok"}

    spec = ToolSpec(
        name="no_args",
        description="No arguments.",
        input_schema={"type": "object"},
        handler=handler,
    )
    server._tools[spec.name] = (spec, object())  # type: ignore[arg-type]

    response = _decode_response(await server._call_tool("no_args", None))

    assert response == {"status": "ok"}


@pytest.mark.asyncio
async def test_call_tool_rejects_non_object_arguments():
    server = ResearchMCPServer()

    def handler() -> dict[str, str]:
        return {"status": "ok"}

    spec = ToolSpec(
        name="object_args_only",
        description="Requires object arguments.",
        input_schema={"type": "object", "properties": {}},
        handler=handler,
    )
    server._tools[spec.name] = (spec, object())  # type: ignore[arg-type]

    response = _decode_response(await server._call_tool("object_args_only", []))  # type: ignore[arg-type]

    assert response["status"] == "validation_error"
    assert response["error_type"] == "invalid_arguments"
    assert response["tool"] == "object_args_only"
    assert "is not of type 'object'" in response["message"]


def test_strict_object_schema_advertises_unknown_argument_rejection():
    server = ResearchMCPServer()
    schema = {"type": "object", "properties": {}}

    strict_schema = server._strict_object_schema(schema)

    assert strict_schema["additionalProperties"] is False
    assert "additionalProperties" not in schema
