"""Engineering simulation adapter for COMSOL, PFC, and Fluent.

This adapter does not reimplement commercial solvers. It exposes a safe MCP
control surface around their existing command-line/batch interfaces.
"""

from __future__ import annotations

import asyncio
import logging
import os
import shlex
from pathlib import Path
from typing import Any
from uuid import uuid4

from research_mcp.adapters import AdapterMeta, BaseAdapter, ToolSpec, register_adapter
from research_mcp.simulation.comsol_backend import ComsolBackend, ComsolServerConfig
from research_mcp.simulation.fluent_backend import FluentBackend, FluentSessionConfig
from research_mcp.simulation.pfc_bridge_backend import (
    PFCBridgeClient,
    PFCBridgeConfig,
    load_bridge_config,
)

logger = logging.getLogger("research-mcp.simulation")


@register_adapter
class SimulationAdapter(BaseAdapter):
    """Run engineering simulation software through configured batch commands."""

    def __init__(self) -> None:
        self.comsol_cmd = "comsol"
        self.fluent_cmd = "fluent"
        self.pfc_cmd = "pfc"
        self.timeout_seconds = 3600
        self._bridge_config: PFCBridgeConfig | None = None
        self._bridge_client: PFCBridgeClient | None = None
        self._comsol_backend = ComsolBackend()
        self._fluent_backend = FluentBackend()

    def metadata(self) -> AdapterMeta:
        return AdapterMeta(
            name="simulation",
            description="Batch control for COMSOL, PFC, and ANSYS Fluent",
            tools=[
                ToolSpec(
                    name="simulation_check_config",
                    description="Show configured command names/paths for COMSOL, PFC, and Fluent.",
                    input_schema={"type": "object", "properties": {}},
                    handler=self.check_config,
                ),
                ToolSpec(
                    name="simulation_workflow_template",
                    description="Create a local simulation workflow checklist.",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "solver": {
                                "type": "string",
                                "enum": ["comsol", "fluent", "pfc", "mixed"],
                                "default": "mixed",
                            },
                            "objective": {"type": "string", "description": "Simulation objective"},
                            "parameters": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Parameter names to sweep",
                            },
                        },
                    },
                    handler=self.workflow_template,
                ),
                ToolSpec(
                    name="comsol_run_batch",
                    description="Run a COMSOL .mph model in batch mode.",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "model_file": {
                                "type": "string",
                                "description": "Path to input .mph model",
                            },
                            "output_file": {
                                "type": "string",
                                "description": "Optional output .mph path",
                            },
                            "study": {
                                "type": "string",
                                "description": "Optional COMSOL study tag/name",
                            },
                            "extra_args": {
                                "type": "string",
                                "description": "Additional command-line args",
                            },
                            "timeout_seconds": {
                                "type": "integer",
                                "description": "Timeout seconds",
                            },
                        },
                        "required": ["model_file"],
                    },
                    handler=self.comsol_run_batch,
                ),
                ToolSpec(
                    name="comsol_parse_table",
                    description="Parse a COMSOL exported table and summarize result columns.",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "table_file": {
                                "type": "string",
                                "description": "CSV or text table exported from COMSOL",
                            },
                            "x_column": {
                                "type": "string",
                                "description": "Optional x/parameter column for plotting",
                            },
                            "output_plot": {
                                "type": "string",
                                "description": "Optional SVG/PNG/PDF plot path",
                            },
                        },
                        "required": ["table_file"],
                    },
                    handler=self.comsol_parse_table,
                ),
                ToolSpec(
                    name="comsol_check_mph",
                    description="Check whether the MPh library is available.",
                    input_schema={"type": "object", "properties": {}},
                    handler=self.comsol_check_mph,
                ),
                ToolSpec(
                    name="comsol_server_connect",
                    description=(
                        "Connect to a running COMSOL Multiphysics Server (attach-first pattern)."
                    ),
                    input_schema={
                        "type": "object",
                        "properties": {
                            "host": {"type": "string", "default": "localhost"},
                            "port": {"type": "integer", "default": 2036},
                            "model_path": {
                                "type": "string",
                                "description": "Optional .mph file to load after connecting",
                            },
                            "timeout_seconds": {"type": "number", "default": 30.0},
                        },
                    },
                    handler=self.comsol_server_connect,
                ),
                ToolSpec(
                    name="comsol_server_disconnect",
                    description="Disconnect from the COMSOL Server and release resources.",
                    input_schema={"type": "object", "properties": {}},
                    handler=self.comsol_server_disconnect,
                ),
                ToolSpec(
                    name="comsol_server_info",
                    description="Show COMSOL connection and model status.",
                    input_schema={"type": "object", "properties": {}},
                    handler=self.comsol_server_info,
                ),
                ToolSpec(
                    name="comsol_model_load",
                    description="Load a .mph model file on the connected COMSOL Server.",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "model_path": {
                                "type": "string",
                                "description": "Path to .mph model file",
                            },
                        },
                        "required": ["model_path"],
                    },
                    handler=self.comsol_model_load,
                ),
                ToolSpec(
                    name="comsol_model_create",
                    description="Create a new empty model on the connected COMSOL Server.",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "default": "Server Model"},
                        },
                    },
                    handler=self.comsol_model_create,
                ),
                ToolSpec(
                    name="comsol_get_parameters",
                    description="Read global parameters from the current COMSOL model.",
                    input_schema={"type": "object", "properties": {}},
                    handler=self.comsol_get_parameters,
                ),
                ToolSpec(
                    name="comsol_set_parameters",
                    description="Set global parameters on the current COMSOL model.",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "parameters": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"},
                                        "expression": {"type": "string"},
                                    },
                                },
                                "description": ' [{"name":"p","expression":"1.5"}]',
                            },
                        },
                        "required": ["parameters"],
                    },
                    handler=self.comsol_set_parameters,
                ),
                ToolSpec(
                    name="comsol_solve",
                    description="Solve the current COMSOL model, optionally for a specific study.",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "study_tag": {
                                "type": "string",
                                "description": "Optional study tag",
                                "default": "",
                            },
                            "async_mode": {
                                "type": "boolean",
                                "description": "Run in background thread",
                                "default": False,
                            },
                        },
                    },
                    handler=self.comsol_solve,
                ),
                ToolSpec(
                    name="comsol_solve_status",
                    description="Poll status of a background COMSOL solve job.",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "job_id": {
                                "type": "string",
                                "description": "Job id from comsol_solve async",
                                "default": "",
                            },
                        },
                    },
                    handler=self.comsol_solve_status,
                ),
                ToolSpec(
                    name="comsol_list_studies",
                    description="List study tags in the current COMSOL model.",
                    input_schema={"type": "object", "properties": {}},
                    handler=self.comsol_list_studies,
                ),
                ToolSpec(
                    name="comsol_inspect_file",
                    description="Inspect a COMSOL-related file for metadata and preview.",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "file_path": {
                                "type": "string",
                                "description": "Path to COMSOL file",
                            },
                            "preview_chars": {
                                "type": "integer",
                                "description": "Preview length",
                                "default": 1000,
                            },
                        },
                        "required": ["file_path"],
                    },
                    handler=self.comsol_inspect_file,
                ),
                ToolSpec(
                    name="fluent_run_journal",
                    description="Run ANSYS Fluent in batch mode with a journal file.",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "journal_file": {
                                "type": "string",
                                "description": "Path to Fluent .jou journal file",
                            },
                            "working_dir": {"type": "string", "description": "Working directory"},
                            "dimension": {"type": "string", "enum": ["2d", "3d"], "default": "3d"},
                            "precision": {"type": "string", "enum": ["sp", "dp"], "default": "dp"},
                            "processors": {
                                "type": "integer",
                                "description": "Parallel processor count",
                                "default": 1,
                            },
                            "extra_args": {
                                "type": "string",
                                "description": "Additional command-line args",
                            },
                            "timeout_seconds": {
                                "type": "integer",
                                "description": "Timeout seconds",
                            },
                        },
                        "required": ["journal_file"],
                    },
                    handler=self.fluent_run_journal,
                ),
                ToolSpec(
                    name="fluent_parse_residuals",
                    description="Parse Fluent residual history and assess convergence.",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "residual_file": {
                                "type": "string",
                                "description": "CSV or whitespace residual file",
                            },
                            "threshold": {
                                "type": "number",
                                "description": "Convergence threshold",
                                "default": 1e-4,
                            },
                            "output_plot": {
                                "type": "string",
                                "description": "Optional SVG/PNG/PDF plot path",
                            },
                        },
                        "required": ["residual_file"],
                    },
                    handler=self.fluent_parse_residuals,
                ),
                ToolSpec(
                    name="fluent_check_pyfluent",
                    description="Check local PyFluent availability for live Fluent control.",
                    input_schema={"type": "object", "properties": {}},
                    handler=self.fluent_check_pyfluent,
                ),
                ToolSpec(
                    name="fluent_launch_session",
                    description="Launch a local Ansys Fluent solver session through PyFluent.",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "precision": {
                                "type": "string",
                                "enum": ["single", "double"],
                                "default": "double",
                            },
                            "dimension": {"type": "string", "enum": ["2d", "3d"], "default": "3d"},
                            "processor_count": {"type": "integer", "default": 1},
                            "working_directory": {
                                "type": "string",
                                "description": "Optional workdir",
                            },
                        },
                    },
                    handler=self.fluent_launch_session,
                ),
                ToolSpec(
                    name="fluent_inspect_file",
                    description="Inspect Fluent case, data, or journal file metadata.",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "file_path": {"type": "string", "description": "Path to Fluent file"},
                            "preview_chars": {
                                "type": "integer",
                                "description": "Journal preview length",
                                "default": 1000,
                            },
                        },
                        "required": ["file_path"],
                    },
                    handler=self.fluent_inspect_file,
                ),
                ToolSpec(
                    name="fluent_list_sessions",
                    description="List live Fluent sessions launched by this MCP process.",
                    input_schema={"type": "object", "properties": {}},
                    handler=self.fluent_list_sessions,
                ),
                ToolSpec(
                    name="fluent_execute_tui",
                    description="Execute Fluent TUI commands in a live PyFluent session.",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "session_id": {"type": "string", "description": "Fluent session id"},
                            "commands": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Fluent TUI commands",
                            },
                        },
                        "required": ["session_id", "commands"],
                    },
                    handler=self.fluent_execute_tui,
                ),
                ToolSpec(
                    name="fluent_close_session",
                    description="Close a live Fluent session launched by this MCP process.",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "session_id": {"type": "string", "description": "Fluent session id"},
                        },
                        "required": ["session_id"],
                    },
                    handler=self.fluent_close_session,
                ),
                ToolSpec(
                    name="pfc_run_script",
                    description="Run a PFC/FISH script through the configured PFC command.",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "script_file": {
                                "type": "string",
                                "description": "Path to PFC/FISH script",
                            },
                            "working_dir": {"type": "string", "description": "Working directory"},
                            "extra_args": {
                                "type": "string",
                                "description": "Additional command-line args",
                            },
                            "timeout_seconds": {
                                "type": "integer",
                                "description": "Timeout seconds",
                            },
                        },
                        "required": ["script_file"],
                    },
                    handler=self.pfc_run_script,
                ),
                ToolSpec(
                    name="pfc_parse_history",
                    description="Parse PFC/DEM history output and summarize each series.",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "history_file": {
                                "type": "string",
                                "description": "CSV or whitespace history file",
                            },
                            "output_plot": {
                                "type": "string",
                                "description": "Optional SVG/PNG/PDF plot path",
                            },
                        },
                        "required": ["history_file"],
                    },
                    handler=self.pfc_parse_history,
                ),
                ToolSpec(
                    name="pfc_bridge_status",
                    description="Check PFC bridge connection status and config.",
                    input_schema={"type": "object", "properties": {}},
                    handler=self.pfc_bridge_status,
                ),
                ToolSpec(
                    name="pfc_execute_code",
                    description=("Execute Python code in a running PFC process via bridge."),
                    input_schema={
                        "type": "object",
                        "properties": {
                            "code": {
                                "type": "string",
                                "description": "Python code to execute in PFC",
                            },
                            "timeout_seconds": {
                                "type": "integer",
                                "description": "Timeout in seconds",
                                "default": 10,
                            },
                        },
                        "required": ["code"],
                    },
                    handler=self.pfc_execute_code,
                ),
                ToolSpec(
                    name="pfc_execute_task",
                    description=(
                        "Submit a Python script for asynchronous execution in PFC via bridge."
                    ),
                    input_schema={
                        "type": "object",
                        "properties": {
                            "entry_script": {
                                "type": "string",
                                "description": "Path to Python script executed inside PFC",
                            },
                            "description": {
                                "type": "string",
                                "description": "Short task description",
                            },
                        },
                        "required": ["entry_script", "description"],
                    },
                    handler=self.pfc_execute_task,
                ),
                ToolSpec(
                    name="pfc_check_task_status",
                    description="Check status and paginated output for a PFC bridge task.",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "task_id": {"type": "string", "description": "Bridge task id"},
                            "skip_newest": {
                                "type": "integer",
                                "description": "Newest output lines to skip",
                                "default": 0,
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum output lines",
                                "default": 64,
                            },
                            "filter_text": {
                                "type": "string",
                                "description": "Optional output line filter",
                            },
                            "wait_seconds": {
                                "type": "number",
                                "description": "Optional wait for task update before rechecking",
                                "default": 1,
                            },
                        },
                        "required": ["task_id"],
                    },
                    handler=self.pfc_check_task_status,
                ),
                ToolSpec(
                    name="pfc_list_tasks",
                    description="List tracked PFC bridge tasks with pagination.",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "skip_newest": {
                                "type": "integer",
                                "description": "Newest tasks to skip",
                                "default": 0,
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum tasks to return",
                                "default": 32,
                            },
                        },
                    },
                    handler=self.pfc_list_tasks,
                ),
                ToolSpec(
                    name="pfc_interrupt_task",
                    description="Request graceful interruption of a running PFC bridge task.",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "task_id": {"type": "string", "description": "Bridge task id"},
                        },
                        "required": ["task_id"],
                    },
                    handler=self.pfc_interrupt_task,
                ),
            ],
        )

    async def initialize(self, config: dict[str, Any] | None = None) -> None:
        cfg = config or {}
        self.comsol_cmd = cfg.get("comsol_cmd") or os.environ.get("COMSOL_CMD", "comsol")
        self.fluent_cmd = cfg.get("fluent_cmd") or os.environ.get("FLUENT_CMD", "fluent")
        self.pfc_cmd = cfg.get("pfc_cmd") or os.environ.get("PFC_CMD", "pfc")
        self.timeout_seconds = int(
            cfg.get("timeout_seconds") or os.environ.get("SIM_TIMEOUT_SECONDS", "3600")
        )
        bridge_cfg = cfg.get("pfc_bridge")
        if bridge_cfg and isinstance(bridge_cfg, dict):
            self._bridge_config = PFCBridgeConfig(
                url=bridge_cfg.get("url", "ws://localhost:9001"),
                reconnect_interval_s=float(bridge_cfg.get("reconnect_interval_s", 0.5)),
                max_retries=int(bridge_cfg.get("max_retries", 2)),
                request_timeout_s=float(bridge_cfg.get("request_timeout_s", 10.0)),
                auto_reconnect=bridge_cfg.get("auto_reconnect", True),
            )
        else:
            self._bridge_config = load_bridge_config()

    async def shutdown(self) -> None:
        if self._bridge_client is not None:
            try:
                await self._bridge_client.disconnect()
            except Exception:
                logger.debug("PFC bridge disconnect skipped during shutdown")
            self._bridge_client = None

    async def check_config(self) -> dict[str, Any]:
        return {
            "comsol_cmd": self.comsol_cmd,
            "fluent_cmd": self.fluent_cmd,
            "pfc_cmd": self.pfc_cmd,
            "timeout_seconds": self.timeout_seconds,
            "env": {
                "COMSOL_CMD": os.environ.get("COMSOL_CMD", ""),
                "FLUENT_CMD": os.environ.get("FLUENT_CMD", ""),
                "PFC_CMD": os.environ.get("PFC_CMD", ""),
            },
        }

    def _get_bridge_config(self) -> PFCBridgeConfig:
        if self._bridge_config is None:
            self._bridge_config = load_bridge_config()
        return self._bridge_config

    async def _get_bridge_client(self) -> PFCBridgeClient:
        if self._bridge_client is None:
            self._bridge_client = PFCBridgeClient(self._get_bridge_config())
        return self._bridge_client

    async def pfc_bridge_status(self) -> dict[str, Any]:
        cfg = self._get_bridge_config()
        connected = self._bridge_client.connected if self._bridge_client else False
        return {
            "bridge_url": cfg.url,
            "connected": connected,
            "auto_reconnect": cfg.auto_reconnect,
            "max_retries": cfg.max_retries,
            "request_timeout_s": cfg.request_timeout_s,
            "env": {
                "PFC_MCP_BRIDGE_URL": os.environ.get("PFC_MCP_BRIDGE_URL", ""),
            },
        }

    async def pfc_execute_code(self, code: str, timeout_seconds: int = 10) -> dict[str, Any]:
        try:
            client = await self._get_bridge_client()
            timeout_ms = timeout_seconds * 1000
            response = await client.execute_code(code=code, timeout_ms=timeout_ms)
        except Exception as exc:
            return self._build_bridge_error("pfc_execute_code", exc)

        status = response.get("status", "unknown")
        message = response.get("message", "")
        partial_output = ((response.get("data") or {}).get("output")) or None
        error_block = response.get("error") or {}

        if status == "terminated":
            return {
                "status": "terminated",
                "reason": message,
                "output": partial_output,
                "action": ("PFC state may be partially modified; verify before retrying"),
            }
        if status == "timeout":
            return {
                "status": "timeout",
                "reason": message,
                "output": partial_output,
                "action": "Reduce code complexity or increase timeout",
            }
        if status == "interrupted":
            return {
                "status": "interrupted",
                "reason": message,
                "output": partial_output,
            }
        if status == "error":
            return {
                "status": "error",
                "code": error_block.get("code", "execute_code_error"),
                "message": error_block.get("message", message),
                "reason": message,
                "output": partial_output,
            }

        data = response.get("data") or {}
        result: dict[str, Any] = {
            "status": "ok",
            "output": data.get("output") or "(no output)",
        }
        if data.get("result") is not None:
            result["result"] = data["result"]
        return result

    async def pfc_execute_task(self, entry_script: str, description: str) -> dict[str, Any]:
        script = self._require_file(entry_script)
        task_id = uuid4().hex[:6]
        try:
            client = await self._get_bridge_client()
            response = await client.execute_task(
                script_path=str(script),
                description=description,
                task_id=task_id,
            )
        except Exception as exc:
            return self._build_bridge_error("pfc_execute_task", exc, task_id=task_id)

        status = response.get("status", "unknown")
        message = response.get("message", "")
        if status != "pending":
            return {
                "status": "submission_failed",
                "task_id": task_id,
                "task_status": status,
                "message": message or "Task submission rejected by bridge",
                "action": "Check script path and bridge logs, then retry",
            }
        return {
            "status": "ok",
            "task_id": task_id,
            "entry_script": str(script),
            "description": description,
            "task_status": "pending",
            "message": message or "submitted",
        }

    async def pfc_check_task_status(
        self,
        task_id: str,
        skip_newest: int = 0,
        limit: int = 64,
        filter_text: str = "",
        wait_seconds: float = 1,
    ) -> dict[str, Any]:
        try:
            client = await self._get_bridge_client()
            terminal_states = {"completed", "failed", "interrupted", "not_found"}
            if wait_seconds > 0:
                client.listen_for_task(task_id)

            response = await client.check_task_status(
                task_id=task_id,
                skip_newest=max(0, skip_newest),
                limit=max(1, min(limit, 500)),
                filter_text=filter_text or None,
            )
            status = response.get("status", "unknown")
            if status not in terminal_states and wait_seconds > 0:
                await client.wait_for_task(task_id, timeout=wait_seconds)
                response = await client.check_task_status(
                    task_id=task_id,
                    skip_newest=max(0, skip_newest),
                    limit=max(1, min(limit, 500)),
                    filter_text=filter_text or None,
                )
            else:
                client.unlisten_task(task_id)
        except Exception as exc:
            return self._build_bridge_error("pfc_check_task_status", exc, task_id=task_id)

        status = response.get("status", "unknown")
        if status == "not_found":
            return {
                "status": "not_found",
                "task_id": task_id,
                "message": "Task not found",
                "action": "Verify task_id or submit a new task",
            }

        data = response.get("data") or {}
        return {
            "status": "ok",
            "task_id": task_id,
            "task_status": status,
            "start_time": data.get("start_time"),
            "end_time": data.get("end_time"),
            "elapsed_time": data.get("elapsed_time"),
            "entry_script": data.get("entry_script") or data.get("script_path"),
            "description": data.get("description"),
            "output": data.get("output") or "(no output)",
            "pagination": data.get("pagination") or response.get("pagination") or {},
            "result": data.get("result"),
            "error": data.get("error"),
        }

    async def pfc_list_tasks(self, skip_newest: int = 0, limit: int = 32) -> dict[str, Any]:
        try:
            client = await self._get_bridge_client()
            response = await client.list_tasks(
                offset=max(0, skip_newest), limit=max(1, min(limit, 200))
            )
        except Exception as exc:
            return self._build_bridge_error("pfc_list_tasks", exc)

        status = response.get("status", "unknown")
        if status != "success":
            return {
                "status": "list_failed",
                "task_status": status,
                "message": response.get("message", "Failed to list tasks"),
                "action": "Check bridge state and retry",
            }
        tasks = response.get("data") or []
        pagination = response.get("pagination") or {}
        return {
            "status": "ok",
            "total_count": pagination.get("total_count", len(tasks)),
            "displayed_count": pagination.get("displayed_count", len(tasks)),
            "has_more": pagination.get("has_more", False),
            "tasks": tasks,
        }

    async def pfc_interrupt_task(self, task_id: str) -> dict[str, Any]:
        try:
            client = await self._get_bridge_client()
            response = await client.interrupt_task(task_id)
        except Exception as exc:
            return self._build_bridge_error("pfc_interrupt_task", exc, task_id=task_id)

        status = response.get("status", "unknown")
        message = response.get("message", "")
        if status == "success":
            return {
                "status": "ok",
                "task_id": task_id,
                "interrupt_requested": True,
                "message": message or "signal sent",
                "next_action": f'call pfc_check_task_status(task_id="{task_id}")',
            }
        return {
            "status": "interrupt_failed",
            "task_id": task_id,
            "task_status": status,
            "message": message or "Interrupt request failed",
            "action": "Check task status and bridge logs",
        }

    def _build_bridge_error(
        self, operation: str, exc: Exception, task_id: str | None = None
    ) -> dict[str, Any]:
        cfg = self._get_bridge_config()
        lowered = str(exc).strip().lower()
        if any(
            phrase in lowered
            for phrase in [
                "connect call failed",
                "connection refused",
                "connection closed",
                "connection lost",
            ]
        ):
            reason = "bridge connection failed"
        elif "timed out" in lowered:
            reason = "bridge request timed out"
        else:
            reason = str(exc).strip() or "unknown bridge error"
        result = {
            "status": "bridge_unavailable",
            "operation": operation,
            "bridge_url": cfg.url,
            "reason": reason,
            "action": ("Start itasca-mcp-bridge in PFC GUI, then retry"),
        }
        if task_id is not None:
            result["task_id"] = task_id
        return result

    async def workflow_template(
        self,
        solver: str = "mixed",
        objective: str = "engineering simulation study",
        parameters: list[str] | None = None,
    ) -> dict[str, Any]:
        params = parameters or [
            "primary_control_parameter",
            "mesh_or_particle_resolution",
            "boundary_condition",
        ]
        solver_tools = {
            "comsol": [
                "comsol_check_mph",
                "comsol_server_connect",
                "comsol_model_load",
                "comsol_get_parameters",
                "comsol_set_parameters",
                "comsol_solve",
                "comsol_run_batch",
                "comsol_parse_table",
            ],
            "fluent": [
                "fluent_check_pyfluent",
                "fluent_launch_session",
                "fluent_inspect_file",
                "fluent_execute_tui",
                "fluent_close_session",
                "fluent_run_journal",
                "fluent_parse_residuals",
            ],
            "pfc": [
                "pfc_run_script",
                "pfc_parse_history",
                "pfc_bridge_status",
                "pfc_execute_code",
                "pfc_execute_task",
                "pfc_check_task_status",
                "pfc_list_tasks",
                "pfc_interrupt_task",
            ],
            "mixed": ["comsol_run_batch", "fluent_run_journal", "pfc_run_script"],
        }.get(solver, ["comsol_run_batch", "fluent_run_journal", "pfc_run_script"])
        return {
            "solver": solver,
            "objective": objective,
            "local_tools": ["simulation_check_config", *solver_tools],
            "parameters": params,
            "steps": [
                "Record solver version, command path, license environment, and workdir.",
                "Create one input file per parameter point or a generator script.",
                "Run the configured local solver command through research-mcp.",
                "Save stdout, stderr, return code, raw outputs, and configuration.",
                "Post-process numeric outputs with plot_csv_columns or plot_xy.",
            ],
            "recommended_outputs": [
                "resolved_parameters.csv",
                "solver_stdout.log",
                "solver_stderr.log",
                "raw_results/",
                "figures/",
            ],
        }

    # ------------------------------------------------------------------
    # COMSOL MPh backend handlers (ported from upstream comsol-mcp)
    # ------------------------------------------------------------------

    async def comsol_check_mph(self) -> dict[str, Any]:
        return self._comsol_backend.check_mph()

    async def comsol_server_connect(
        self,
        host: str = "localhost",
        port: int = 2036,
        model_path: str = "",
        timeout_seconds: float = 30.0,
    ) -> dict[str, Any]:
        config = ComsolServerConfig(
            host=host,
            port=port,
            connect_timeout_s=timeout_seconds,
            model_path=model_path,
        )
        return self._comsol_backend.server_connect(config)

    async def comsol_server_disconnect(self) -> dict[str, Any]:
        return self._comsol_backend.server_disconnect()

    async def comsol_server_info(self) -> dict[str, Any]:
        return self._comsol_backend.server_info()

    async def comsol_model_load(self, model_path: str) -> dict[str, Any]:
        return self._comsol_backend.model_load(model_path)

    async def comsol_model_create(self, name: str = "Server Model") -> dict[str, Any]:
        return self._comsol_backend.model_create(name)

    async def comsol_get_parameters(self) -> dict[str, Any]:
        return self._comsol_backend.get_parameters()

    async def comsol_set_parameters(self, parameters: list[dict[str, str]]) -> dict[str, Any]:
        return self._comsol_backend.set_parameters(parameters)

    async def comsol_solve(self, study_tag: str = "", async_mode: bool = False) -> dict[str, Any]:
        if async_mode:
            return self._comsol_backend.solve_async(study_tag)
        return self._comsol_backend.solve(study_tag)

    async def comsol_solve_status(self, job_id: str = "") -> dict[str, Any]:
        return self._comsol_backend.solve_status(job_id)

    async def comsol_list_studies(self) -> dict[str, Any]:
        return self._comsol_backend.list_studies()

    async def comsol_inspect_file(
        self, file_path: str, preview_chars: int = 1000
    ) -> dict[str, Any]:
        return self._comsol_backend.inspect_file(
            file_path=file_path,
            preview_chars=max(0, min(preview_chars, 10000)),
        )

    # ------------------------------------------------------------------
    # COMSOL batch / table fallback
    # ------------------------------------------------------------------

    async def comsol_run_batch(
        self,
        model_file: str,
        output_file: str = "",
        study: str = "",
        extra_args: str = "",
        timeout_seconds: int = 0,
    ) -> dict[str, Any]:
        model = self._require_file(model_file)
        args = [self.comsol_cmd, "batch", "-inputfile", str(model)]
        if output_file:
            args.extend(["-outputfile", output_file])
        if study:
            args.extend(["-study", study])
        args.extend(shlex.split(extra_args))
        return await self._run(args, model.parent, timeout_seconds or self.timeout_seconds)

    async def comsol_parse_table(
        self,
        table_file: str,
        x_column: str = "",
        output_plot: str = "",
    ) -> dict[str, Any]:
        path = self._require_file(table_file)
        data = self._parse_numeric_table(path)
        independent = x_column or next(iter(data))
        if independent not in data:
            raise ValueError(f"Unknown x_column: {independent}")
        series = {name: values for name, values in data.items() if name != independent}
        summaries = {name: self._summarize_series(values) for name, values in series.items()}
        plot_path = ""
        if output_plot:
            plot_path = self._plot_history(data, independent, output_plot)
        return {
            "table_file": str(path),
            "x_column": independent,
            "rows": len(data[independent]),
            "columns": list(data),
            "result_columns": list(series),
            "summaries": summaries,
            "output_plot": plot_path,
        }

    def _parse_numeric_table(self, path: Path) -> dict[str, list[float]]:
        import csv

        lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines()]
        lines = [
            line.lstrip("%").strip() for line in lines if line and not line.startswith(("#", ";"))
        ]
        lines = [line for line in lines if line]
        if not lines:
            raise ValueError(f"Table file is empty: {path}")
        delimiter = "," if "," in lines[0] else None
        rows = list(csv.reader(lines, delimiter=delimiter or " ", skipinitialspace=True))
        rows = [[cell for cell in row if cell] for row in rows]
        first = rows[0]
        if self._is_numeric_row(first):
            header = [f"column_{index + 1}" for index in range(len(first))]
            numeric_rows = rows
        else:
            header = [
                self._normalize_residual_name(name, index) for index, name in enumerate(first)
            ]
            numeric_rows = rows[1:]
        columns = {name: [] for name in header}
        for row in numeric_rows:
            if len(row) < len(header):
                continue
            for name, value in zip(header, row):
                columns[name].append(float(value))
        return columns

    async def fluent_check_pyfluent(self) -> dict[str, Any]:
        return self._fluent_backend.check_pyfluent()

    async def fluent_launch_session(
        self,
        precision: str = "double",
        dimension: str = "3d",
        processor_count: int = 1,
        working_directory: str = "",
    ) -> dict[str, Any]:
        config = FluentSessionConfig(
            precision=precision,
            dimension=dimension,
            processor_count=processor_count,
            working_directory=working_directory,
        )
        return self._fluent_backend.launch_session(config)

    async def fluent_inspect_file(
        self, file_path: str, preview_chars: int = 1000
    ) -> dict[str, Any]:
        return self._fluent_backend.inspect_file(
            file_path=file_path,
            preview_chars=max(0, min(preview_chars, 10000)),
        )

    async def fluent_list_sessions(self) -> dict[str, Any]:
        return self._fluent_backend.list_sessions()

    async def fluent_execute_tui(self, session_id: str, commands: list[str]) -> dict[str, Any]:
        return self._fluent_backend.execute_tui(session_id=session_id, commands=commands)

    async def fluent_close_session(self, session_id: str) -> dict[str, Any]:
        return self._fluent_backend.close_session(session_id)

    async def fluent_run_journal(
        self,
        journal_file: str,
        working_dir: str = "",
        dimension: str = "3d",
        precision: str = "dp",
        processors: int = 1,
        extra_args: str = "",
        timeout_seconds: int = 0,
    ) -> dict[str, Any]:
        journal = self._require_file(journal_file)
        workdir = Path(working_dir).resolve() if working_dir else journal.parent
        mode = f"{dimension}{precision}"
        args = [self.fluent_cmd, mode, "-g", "-i", str(journal)]
        if processors > 1:
            args.extend(["-t", str(processors)])
        args.extend(shlex.split(extra_args))
        return await self._run(args, workdir, timeout_seconds or self.timeout_seconds)

    async def fluent_parse_residuals(
        self,
        residual_file: str,
        threshold: float = 1e-4,
        output_plot: str = "",
    ) -> dict[str, Any]:
        path = self._require_file(residual_file)
        data = self._parse_residual_table(path)
        series = {name: values for name, values in data.items() if name != "iteration"}
        final_values = {name: values[-1] for name, values in series.items() if values}
        converged = bool(final_values) and all(
            value <= threshold for value in final_values.values()
        )
        plot_path = ""
        if output_plot:
            plot_path = self._plot_residuals(data, output_plot)
        return {
            "residual_file": str(path),
            "iterations": len(data.get("iteration", [])),
            "residual_names": list(series),
            "final_residuals": final_values,
            "threshold": threshold,
            "converged": converged,
            "output_plot": plot_path,
        }

    def _parse_residual_table(self, path: Path) -> dict[str, list[float]]:
        import csv

        lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines()]
        lines = [line for line in lines if line and not line.startswith(("#", ";"))]
        if not lines:
            raise ValueError(f"Residual file is empty: {path}")
        delimiter = "," if "," in lines[0] else None
        rows = list(csv.reader(lines, delimiter=delimiter or " ", skipinitialspace=True))
        rows = [[cell for cell in row if cell] for row in rows]
        header, numeric_rows = self._split_residual_header(rows)
        columns = {name: [] for name in header}
        for row in numeric_rows:
            if len(row) < len(header):
                continue
            for name, value in zip(header, row):
                columns[name].append(float(value))
        if not columns.get("iteration"):
            columns["iteration"] = [float(index + 1) for index in range(len(numeric_rows))]
        return columns

    def _split_residual_header(self, rows: list[list[str]]) -> tuple[list[str], list[list[str]]]:
        first = rows[0]
        if self._is_numeric_row(first):
            names = ["iteration", *[f"residual_{index}" for index in range(1, len(first))]]
            return names, rows
        names = [self._normalize_residual_name(name, index) for index, name in enumerate(first)]
        if names and names[0] not in {"iteration", "iter", "time_step"}:
            names[0] = "iteration"
        else:
            names[0] = "iteration"
        return names, rows[1:]

    def _is_numeric_row(self, row: list[str]) -> bool:
        try:
            [float(value) for value in row]
            return True
        except ValueError:
            return False

    def _normalize_residual_name(self, name: str, index: int) -> str:
        normalized = name.strip().lower().replace(" ", "_").replace("-", "_")
        return normalized or f"residual_{index}"

    def _plot_residuals(self, data: dict[str, list[float]], output_plot: str) -> str:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        output = Path(output_plot).expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        iterations = data.get("iteration", [])
        fig, ax = plt.subplots(figsize=(5.4, 3.6), constrained_layout=True)
        for name, values in data.items():
            if name == "iteration" or not values:
                continue
            ax.semilogy(iterations[: len(values)], values, label=name)
        ax.set_xlabel("Iteration")
        ax.set_ylabel("Residual")
        ax.grid(True, which="both", alpha=0.25)
        ax.legend(fontsize=8)
        fig.savefig(output, dpi=300)
        plt.close(fig)
        return str(output)

    async def pfc_run_script(
        self,
        script_file: str,
        working_dir: str = "",
        extra_args: str = "",
        timeout_seconds: int = 0,
    ) -> dict[str, Any]:
        script = self._require_file(script_file)
        workdir = Path(working_dir).resolve() if working_dir else script.parent
        args = [self.pfc_cmd, str(script)]
        args.extend(shlex.split(extra_args))
        return await self._run(args, workdir, timeout_seconds or self.timeout_seconds)

    async def pfc_parse_history(
        self,
        history_file: str,
        output_plot: str = "",
    ) -> dict[str, Any]:
        path = self._require_file(history_file)
        data = self._parse_residual_table(path)
        independent = "iteration" if "iteration" in data else next(iter(data))
        series = {name: values for name, values in data.items() if name != independent}
        summaries = {name: self._summarize_series(values) for name, values in series.items()}
        plot_path = ""
        if output_plot:
            plot_path = self._plot_history(data, independent, output_plot)
        return {
            "history_file": str(path),
            "independent_column": independent,
            "rows": len(data.get(independent, [])),
            "series_names": list(series),
            "summaries": summaries,
            "output_plot": plot_path,
        }

    def _summarize_series(self, values: list[float]) -> dict[str, float]:
        if not values:
            return {"min": 0.0, "max": 0.0, "mean": 0.0, "final": 0.0}
        return {
            "min": min(values),
            "max": max(values),
            "mean": sum(values) / len(values),
            "final": values[-1],
        }

    def _plot_history(
        self,
        data: dict[str, list[float]],
        independent: str,
        output_plot: str,
    ) -> str:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        output = Path(output_plot).expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        x_values = data.get(independent, [])
        fig, ax = plt.subplots(figsize=(5.4, 3.6), constrained_layout=True)
        for name, values in data.items():
            if name == independent or not values:
                continue
            ax.plot(x_values[: len(values)], values, label=name)
        ax.set_xlabel(independent)
        ax.set_ylabel("Value")
        ax.grid(True, alpha=0.25)
        ax.legend(fontsize=8)
        fig.savefig(output, dpi=300)
        plt.close(fig)
        return str(output)

    def _require_file(self, file_path: str) -> Path:
        path = Path(file_path).expanduser().resolve()
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(f"File not found: {path}")
        return path

    async def _run(self, args: list[str], cwd: Path, timeout_seconds: int) -> dict[str, Any]:
        proc = await asyncio.create_subprocess_exec(
            *args,
            cwd=str(cwd),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_seconds)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return {
                "status": "timeout",
                "command": args,
                "cwd": str(cwd),
                "timeout_seconds": timeout_seconds,
            }
        return {
            "status": "ok" if proc.returncode == 0 else "failed",
            "returncode": proc.returncode,
            "command": args,
            "cwd": str(cwd),
            "stdout": stdout.decode(errors="replace")[-8000:],
            "stderr": stderr.decode(errors="replace")[-8000:],
        }
