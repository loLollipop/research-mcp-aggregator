"""Internal PFC bridge backend adapted from upstream pfc-mcp bridge client.

Ported from vendored pfc-mcp/src/pfc_mcp/bridge/client.py (MIT license).
Adapted for research-mcp: standalone backend, no global MCP server dependency.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

logger = logging.getLogger("research-mcp.pfc-bridge")


@dataclass(frozen=True)
class PFCBridgeConfig:
    url: str = "ws://localhost:9001"
    reconnect_interval_s: float = 0.5
    max_retries: int = 2
    request_timeout_s: float = 10.0
    auto_reconnect: bool = True


def load_bridge_config() -> PFCBridgeConfig:
    def env_bool(name: str, default: bool) -> bool:
        value = os.getenv(name)
        if value is None:
            return default
        return value.strip().lower() in {"1", "true", "yes", "on"}

    def env_float(name: str, default: float) -> float:
        value = os.getenv(name)
        if value is None:
            return default
        try:
            return float(value)
        except ValueError:
            return default

    def env_int(name: str, default: int) -> int:
        value = os.getenv(name)
        if value is None:
            return default
        try:
            return int(value)
        except ValueError:
            return default

    return PFCBridgeConfig(
        url=os.getenv("PFC_MCP_BRIDGE_URL", "ws://localhost:9001"),
        reconnect_interval_s=env_float("PFC_MCP_RECONNECT_INTERVAL_S", 0.5),
        max_retries=max(0, env_int("PFC_MCP_MAX_RETRIES", 2)),
        request_timeout_s=max(1.0, env_float("PFC_MCP_REQUEST_TIMEOUT_S", 10.0)),
        auto_reconnect=env_bool("PFC_MCP_AUTO_RECONNECT", True),
    )


class PFCBridgeClient:
    """Async WebSocket client for itasca-mcp-bridge."""

    def __init__(self, config: PFCBridgeConfig) -> None:
        self.config = config
        self._websocket: Any | None = None
        self._receiver_task: asyncio.Task[Any] | None = None
        self._pending_requests: dict[str, asyncio.Future[dict[str, Any]]] = {}
        self._task_events: dict[str, asyncio.Event] = {}
        self._lock = asyncio.Lock()

    @property
    def connected(self) -> bool:
        return self._websocket is not None

    async def connect(self) -> None:
        async with self._lock:
            if self._websocket is not None:
                return
            import websockets

            self._websocket = await websockets.connect(
                self.config.url, compression=None, max_size=50 * 2**20
            )
            self._receiver_task = asyncio.create_task(self._receive_loop())
            logger.info("Connected to PFC bridge at %s", self.config.url)

    async def disconnect(self) -> None:
        async with self._lock:
            receiver_task = self._receiver_task
            websocket = self._websocket
            self._receiver_task = None
            self._websocket = None

        if receiver_task is not None:
            receiver_task.cancel()
            try:
                await receiver_task
            except asyncio.CancelledError:
                pass

        if websocket is not None:
            try:
                await websocket.close()
            except Exception:
                pass

        self._fail_pending(ConnectionError("Connection closed"))

    def _fail_pending(self, exc: Exception) -> None:
        pending = list(self._pending_requests.values())
        self._pending_requests.clear()
        for future in pending:
            if not future.done():
                future.set_exception(exc)

    async def _receive_loop(self) -> None:
        assert self._websocket is not None
        try:
            async for raw_message in self._websocket:
                payload = json.loads(raw_message)
                msg_type = payload.get("type")

                if msg_type == "task_status_changed":
                    task_id = payload.get("task_id", "")
                    event = self._task_events.get(task_id)
                    if event:
                        event.set()
                    continue

                if msg_type not in {"result", "execute_code_result"}:
                    continue
                request_id = payload.get("request_id")
                if not request_id:
                    continue
                future = self._pending_requests.pop(request_id, None)
                if future and not future.done():
                    future.set_result(payload)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("Bridge receive loop stopped: %s", exc)
        finally:
            async with self._lock:
                self._websocket = None
                self._receiver_task = None
            self._fail_pending(ConnectionError("Bridge connection lost"))

    async def _send_request(self, message: dict[str, Any], timeout_s: float) -> dict[str, Any]:
        await self._ensure_connected()
        assert self._websocket is not None

        request_id = message.get("request_id") or str(uuid4())
        message["request_id"] = request_id

        loop = asyncio.get_event_loop()
        future: asyncio.Future[dict[str, Any]] = loop.create_future()
        self._pending_requests[request_id] = future

        try:
            await self._websocket.send(json.dumps(message))
            return await asyncio.wait_for(future, timeout=timeout_s)
        except asyncio.TimeoutError as exc:
            self._pending_requests.pop(request_id, None)
            raise TimeoutError(f"Bridge request timed out after {timeout_s:.1f}s") from exc

    async def _ensure_connected(self) -> None:
        if self.connected:
            return
        await self.connect()

    async def _request_with_retry(
        self,
        message: dict[str, Any],
        operation_name: str,
        timeout_s: float | None = None,
    ) -> dict[str, Any]:
        timeout = timeout_s if timeout_s is not None else self.config.request_timeout_s
        attempts = self.config.max_retries + 1
        last_error: Exception | None = None

        for attempt in range(1, attempts + 1):
            try:
                return await self._send_request(message, timeout)
            except Exception as exc:
                last_error = exc
                await self.disconnect()
                if not self.config.auto_reconnect or attempt >= attempts:
                    break
                await asyncio.sleep(self.config.reconnect_interval_s)

        assert last_error is not None
        raise ConnectionError(f"{operation_name} failed: {last_error}") from last_error

    async def ping(self) -> dict[str, Any]:
        return await self._request_with_retry(
            {"type": "ping"}, operation_name="ping", timeout_s=5.0
        )

    async def execute_code(self, code: str, timeout_ms: int = 10000) -> dict[str, Any]:
        timeout_s = max(self.config.request_timeout_s, timeout_ms / 1000.0 + 5.0)
        return await self._request_with_retry(
            {"type": "execute_code", "code": code, "timeout_ms": timeout_ms},
            operation_name="execute_code",
            timeout_s=timeout_s,
        )

    async def execute_task(
        self, script_path: str, description: str, task_id: str
    ) -> dict[str, Any]:
        return await self._request_with_retry(
            {
                "type": "execute_task",
                "task_id": task_id,
                "script_path": script_path,
                "description": description,
                "source": "research-mcp",
            },
            operation_name="execute_task",
            timeout_s=10.0,
        )

    async def check_task_status(
        self,
        task_id: str,
        skip_newest: int = 0,
        limit: int = 64,
        filter_text: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "type": "check_task_status",
            "task_id": task_id,
            "skip_newest": skip_newest,
            "limit": limit,
        }
        if filter_text is not None:
            payload["filter_text"] = filter_text
        return await self._request_with_retry(payload, operation_name="check_task_status")

    async def list_tasks(self, offset: int, limit: int | None) -> dict[str, Any]:
        return await self._request_with_retry(
            {"type": "list_tasks", "offset": offset, "limit": limit},
            operation_name="list_tasks",
        )

    async def interrupt_task(self, task_id: str) -> dict[str, Any]:
        return await self._request_with_retry(
            {"type": "interrupt_task", "task_id": task_id},
            operation_name="interrupt_task",
            timeout_s=5.0,
        )

    async def get_working_directory(self) -> str | None:
        response = await self._request_with_retry(
            {"type": "get_working_directory"},
            operation_name="get_working_directory",
        )
        if response.get("status") != "success":
            return None
        data = response.get("data") or {}
        return data.get("working_directory")

    def listen_for_task(self, task_id: str) -> None:
        if task_id not in self._task_events:
            self._task_events[task_id] = asyncio.Event()

    def unlisten_task(self, task_id: str) -> None:
        self._task_events.pop(task_id, None)

    async def wait_for_task(self, task_id: str, timeout: float) -> bool:
        event = self._task_events.get(task_id)
        if event is None:
            return False
        try:
            await asyncio.wait_for(event.wait(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            return False
        finally:
            self._task_events.pop(task_id, None)
