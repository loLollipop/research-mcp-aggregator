"""Tests for PFC bridge backend and bridge-exposed tools."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from research_mcp.adapters.simulation_adapter import SimulationAdapter
from research_mcp.server import ResearchMCPServer
from research_mcp.simulation.pfc_bridge_backend import (
    PFCBridgeClient,
    PFCBridgeConfig,
    load_bridge_config,
)

# --- Backend unit tests ---


def test_load_bridge_config_defaults():
    cfg = load_bridge_config()
    assert cfg.url == "ws://localhost:9001"
    assert cfg.max_retries >= 0
    assert cfg.request_timeout_s >= 1.0


def test_bridge_config_from_env(monkeypatch):
    monkeypatch.setenv("PFC_MCP_BRIDGE_URL", "ws://127.0.0.1:9999")
    monkeypatch.setenv("PFC_MCP_MAX_RETRIES", "5")
    monkeypatch.setenv("PFC_MCP_REQUEST_TIMEOUT_S", "30.0")
    cfg = load_bridge_config()
    assert cfg.url == "ws://127.0.0.1:9999"
    assert cfg.max_retries == 5
    assert cfg.request_timeout_s == 30.0


def test_bridge_client_not_connected_by_default():
    cfg = PFCBridgeConfig(url="ws://localhost:9001")
    client = PFCBridgeClient(cfg)
    assert client.connected is False


# --- Adapter integration tests ---


@pytest.mark.asyncio
async def test_pfc_bridge_status_returns_config():
    adapter = SimulationAdapter()
    await adapter.initialize({})
    status = await adapter.pfc_bridge_status()
    assert status["bridge_url"] == "ws://localhost:9001"
    assert status["connected"] is False
    assert "auto_reconnect" in status


@pytest.mark.asyncio
async def test_pfc_bridge_status_with_custom_config():
    adapter = SimulationAdapter()
    await adapter.initialize(
        {
            "pfc_bridge": {
                "url": "ws://127.0.0.1:9999",
                "max_retries": 3,
                "request_timeout_s": 20.0,
            }
        }
    )
    status = await adapter.pfc_bridge_status()
    assert status["bridge_url"] == "ws://127.0.0.1:9999"
    assert status["max_retries"] == 3
    assert status["request_timeout_s"] == 20.0


@pytest.mark.asyncio
async def test_pfc_execute_code_bridge_unavailable():
    adapter = SimulationAdapter()
    await adapter.initialize({})
    result = await adapter.pfc_execute_code("print('hello')")
    assert result["status"] == "bridge_unavailable"
    assert "bridge_url" in result
    assert result["action"] == "Start itasca-mcp-bridge in PFC GUI, then retry"


@pytest.mark.asyncio
async def test_pfc_execute_code_with_mock_bridge():
    adapter = SimulationAdapter()
    await adapter.initialize({})

    mock_client = MagicMock()
    mock_client.connected = True
    mock_client.execute_code = AsyncMock(
        return_value={
            "status": "success",
            "data": {"output": "hello world", "result": None},
        }
    )
    adapter._bridge_client = mock_client

    result = await adapter.pfc_execute_code("print('hello')")
    assert result["status"] == "ok"
    assert result["output"] == "hello world"
    mock_client.execute_code.assert_awaited_once_with(code="print('hello')", timeout_ms=10000)


@pytest.mark.asyncio
async def test_pfc_execute_code_with_mock_bridge_timeout():
    adapter = SimulationAdapter()
    await adapter.initialize({})

    mock_client = MagicMock()
    mock_client.connected = True
    mock_client.execute_code = AsyncMock(
        return_value={
            "status": "timeout",
            "message": "execution timed out",
            "data": {"output": "partial output"},
        }
    )
    adapter._bridge_client = mock_client

    result = await adapter.pfc_execute_code("import time; time.sleep(999)")
    assert result["status"] == "timeout"
    assert result["output"] == "partial output"


@pytest.mark.asyncio
async def test_pfc_execute_code_with_mock_bridge_error():
    adapter = SimulationAdapter()
    await adapter.initialize({})

    mock_client = MagicMock()
    mock_client.connected = True
    mock_client.execute_code = AsyncMock(
        return_value={
            "status": "error",
            "error": {"code": "exec_error", "message": "SyntaxError"},
            "message": "error",
        }
    )
    adapter._bridge_client = mock_client

    result = await adapter.pfc_execute_code("bad code !!!")
    assert result["status"] == "error"
    assert result["code"] == "exec_error"


@pytest.mark.asyncio
async def test_pfc_execute_task_with_mock_bridge(tmp_path):
    script = tmp_path / "task.py"
    script.write_text("print('run')\n", encoding="utf-8")
    adapter = SimulationAdapter()
    await adapter.initialize({})

    mock_client = MagicMock()
    mock_client.connected = True
    mock_client.execute_task = AsyncMock(return_value={"status": "pending", "message": "queued"})
    adapter._bridge_client = mock_client

    with patch("research_mcp.adapters.simulation_adapter.uuid4") as mock_uuid4:
        mock_uuid4.return_value.hex = "abcdef123456"
        result = await adapter.pfc_execute_task(str(script), "demo task")

    assert result["status"] == "ok"
    assert result["task_id"] == "abcdef"
    assert result["task_status"] == "pending"
    mock_client.execute_task.assert_awaited_once_with(
        script_path=str(script.resolve()),
        description="demo task",
        task_id="abcdef",
    )


@pytest.mark.asyncio
async def test_pfc_execute_task_rejected_by_bridge(tmp_path):
    script = tmp_path / "task.py"
    script.write_text("print('run')\n", encoding="utf-8")
    adapter = SimulationAdapter()
    await adapter.initialize({})

    mock_client = MagicMock()
    mock_client.connected = True
    mock_client.execute_task = AsyncMock(
        return_value={"status": "failed", "message": "script not accepted"}
    )
    adapter._bridge_client = mock_client

    result = await adapter.pfc_execute_task(str(script), "demo task")
    assert result["status"] == "submission_failed"
    assert result["task_status"] == "failed"


@pytest.mark.asyncio
async def test_pfc_check_task_status_with_mock_bridge():
    adapter = SimulationAdapter()
    await adapter.initialize({})

    mock_client = MagicMock()
    mock_client.connected = True
    mock_client.listen_for_task = MagicMock()
    mock_client.unlisten_task = MagicMock()
    mock_client.wait_for_task = AsyncMock(return_value=True)
    mock_client.check_task_status = AsyncMock(
        side_effect=[
            {"status": "running", "data": {"output": "step 1"}},
            {
                "status": "completed",
                "data": {
                    "output": "done",
                    "pagination": {"total_lines": 1, "line_range": [1, 1]},
                    "result": {"value": 1},
                },
            },
        ]
    )
    adapter._bridge_client = mock_client

    result = await adapter.pfc_check_task_status("abc123", wait_seconds=0.1)
    assert result["status"] == "ok"
    assert result["task_status"] == "completed"
    assert result["output"] == "done"
    assert result["result"] == {"value": 1}
    mock_client.listen_for_task.assert_called_once_with("abc123")
    mock_client.wait_for_task.assert_awaited_once_with("abc123", timeout=0.1)
    assert mock_client.check_task_status.await_count == 2


@pytest.mark.asyncio
async def test_pfc_check_task_status_not_found():
    adapter = SimulationAdapter()
    await adapter.initialize({})

    mock_client = MagicMock()
    mock_client.connected = True
    mock_client.listen_for_task = MagicMock()
    mock_client.unlisten_task = MagicMock()
    mock_client.check_task_status = AsyncMock(return_value={"status": "not_found", "data": {}})
    adapter._bridge_client = mock_client

    result = await adapter.pfc_check_task_status("missing", wait_seconds=0)
    assert result["status"] == "not_found"
    assert result["task_id"] == "missing"


@pytest.mark.asyncio
async def test_pfc_list_tasks_with_mock_bridge():
    adapter = SimulationAdapter()
    await adapter.initialize({})

    mock_client = MagicMock()
    mock_client.connected = True
    mock_client.list_tasks = AsyncMock(
        return_value={
            "status": "success",
            "data": [{"task_id": "abc123", "status": "completed"}],
            "pagination": {"total_count": 1, "displayed_count": 1, "has_more": False},
        }
    )
    adapter._bridge_client = mock_client

    result = await adapter.pfc_list_tasks(skip_newest=0, limit=10)
    assert result["status"] == "ok"
    assert result["total_count"] == 1
    assert result["tasks"][0]["task_id"] == "abc123"
    mock_client.list_tasks.assert_awaited_once_with(offset=0, limit=10)


@pytest.mark.asyncio
async def test_pfc_interrupt_task_with_mock_bridge():
    adapter = SimulationAdapter()
    await adapter.initialize({})

    mock_client = MagicMock()
    mock_client.connected = True
    mock_client.interrupt_task = AsyncMock(
        return_value={"status": "success", "message": "signal sent"}
    )
    adapter._bridge_client = mock_client

    result = await adapter.pfc_interrupt_task("abc123")
    assert result["status"] == "ok"
    assert result["interrupt_requested"] is True
    mock_client.interrupt_task.assert_awaited_once_with("abc123")


@pytest.mark.asyncio
async def test_pfc_interrupt_task_failed_by_bridge():
    adapter = SimulationAdapter()
    await adapter.initialize({})

    mock_client = MagicMock()
    mock_client.connected = True
    mock_client.interrupt_task = AsyncMock(
        return_value={"status": "not_found", "message": "missing"}
    )
    adapter._bridge_client = mock_client

    result = await adapter.pfc_interrupt_task("missing")
    assert result["status"] == "interrupt_failed"
    assert result["task_status"] == "not_found"


# --- Tool registration test ---


@pytest.mark.asyncio
async def test_server_registers_pfc_bridge_tools():
    server = ResearchMCPServer()
    await server.initialize()
    try:
        tool_names = set(server._tools)
        assert "pfc_bridge_status" in tool_names
        assert "pfc_execute_code" in tool_names
        assert "pfc_execute_task" in tool_names
        assert "pfc_check_task_status" in tool_names
        assert "pfc_list_tasks" in tool_names
        assert "pfc_interrupt_task" in tool_names
        assert "pfc_docs_status" in tool_names
        assert "pfc_browse_commands" in tool_names
        assert "pfc_browse_python_api" in tool_names
        assert "mcp_bridge_status" not in tool_names
        assert not any("__" in name for name in tool_names)
    finally:
        await server.shutdown()
