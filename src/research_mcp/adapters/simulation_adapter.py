"""Engineering simulation adapter for COMSOL, PFC, and Fluent.

This adapter does not reimplement commercial solvers. It exposes a safe MCP
control surface around their existing command-line/batch interfaces.
"""

from __future__ import annotations

import logging
import os
from typing import Any
from uuid import uuid4

from research_mcp.adapters import AdapterMeta, BaseAdapter, register_adapter
from research_mcp.simulation.command_utils import (
    COMSOL_MODEL_SUFFIXES,
    require_file,
    resolve_output_path,
    resolve_working_dir,
    run_command,
    split_extra_args,
    validate_executable_command,
)
from research_mcp.simulation.comsol_backend import ComsolBackend, ComsolServerConfig
from research_mcp.simulation.fluent_backend import FluentBackend, FluentSessionConfig
from research_mcp.simulation.parsers import (
    parse_numeric_table,
    parse_residual_table,
    summarize_series,
)
from research_mcp.simulation.pfc_bridge_backend import (
    PFCBridgeClient,
    PFCBridgeConfig,
    load_bridge_config,
)
from research_mcp.simulation.plotting import plot_history, plot_residuals
from research_mcp.simulation.tool_specs import build_simulation_tools
from research_mcp.simulation.workflow_templates import build_workflow_template

logger = logging.getLogger("research-mcp.simulation")


@register_adapter
class SimulationAdapter(BaseAdapter):
    """Run engineering simulation software through configured batch commands."""

    adapter_name = "simulation"

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
            tools=build_simulation_tools(self),
        )

    async def initialize(self, config: dict[str, Any] | None = None) -> None:
        cfg = config or {}
        self.comsol_cmd = validate_executable_command(
            cfg.get("comsol_cmd") or os.environ.get("COMSOL_CMD", "comsol")
        )
        self.fluent_cmd = validate_executable_command(
            cfg.get("fluent_cmd") or os.environ.get("FLUENT_CMD", "fluent")
        )
        self.pfc_cmd = validate_executable_command(
            cfg.get("pfc_cmd") or os.environ.get("PFC_CMD", "pfc")
        )
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
        script = require_file(entry_script)
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
        return build_workflow_template(solver, objective, parameters)

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
        model = require_file(model_file)
        args = [self.comsol_cmd, "batch", "-inputfile", str(model)]
        if output_file:
            output = resolve_output_path(
                output_file,
                default_dir=model.parent,
                allowed_suffixes=COMSOL_MODEL_SUFFIXES,
            )
            args.extend(["-outputfile", str(output)])
        if study:
            args.extend(["-study", study])
        args.extend(split_extra_args(extra_args))
        return await run_command(args, model.parent, timeout_seconds or self.timeout_seconds)

    async def comsol_parse_table(
        self,
        table_file: str,
        x_column: str = "",
        output_plot: str = "",
    ) -> dict[str, Any]:
        path = require_file(table_file)
        data = parse_numeric_table(path)
        independent = x_column or next(iter(data))
        if independent not in data:
            raise ValueError(f"Unknown x_column: {independent}")
        series = {name: values for name, values in data.items() if name != independent}
        summaries = {name: summarize_series(values) for name, values in series.items()}
        plot_path = ""
        if output_plot:
            plot_path = plot_history(data, independent, output_plot)
        return {
            "table_file": str(path),
            "x_column": independent,
            "rows": len(data[independent]),
            "columns": list(data),
            "result_columns": list(series),
            "summaries": summaries,
            "output_plot": plot_path,
        }

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
        journal = require_file(journal_file)
        workdir = resolve_working_dir(working_dir, journal.parent)
        mode = f"{dimension}{precision}"
        args = [self.fluent_cmd, mode, "-g", "-i", str(journal)]
        if processors > 1:
            args.extend(["-t", str(processors)])
        args.extend(split_extra_args(extra_args))
        return await run_command(args, workdir, timeout_seconds or self.timeout_seconds)

    async def fluent_parse_residuals(
        self,
        residual_file: str,
        threshold: float = 1e-4,
        output_plot: str = "",
    ) -> dict[str, Any]:
        path = require_file(residual_file)
        data = parse_residual_table(path)
        series = {name: values for name, values in data.items() if name != "iteration"}
        final_values = {name: values[-1] for name, values in series.items() if values}
        converged = bool(final_values) and all(
            value <= threshold for value in final_values.values()
        )
        plot_path = ""
        if output_plot:
            plot_path = plot_residuals(data, output_plot)
        return {
            "residual_file": str(path),
            "iterations": len(data.get("iteration", [])),
            "residual_names": list(series),
            "final_residuals": final_values,
            "threshold": threshold,
            "converged": converged,
            "output_plot": plot_path,
        }

    async def pfc_run_script(
        self,
        script_file: str,
        working_dir: str = "",
        extra_args: str = "",
        timeout_seconds: int = 0,
    ) -> dict[str, Any]:
        script = require_file(script_file)
        workdir = resolve_working_dir(working_dir, script.parent)
        args = [self.pfc_cmd, str(script)]
        args.extend(split_extra_args(extra_args))
        return await run_command(args, workdir, timeout_seconds or self.timeout_seconds)

    async def pfc_parse_history(
        self,
        history_file: str,
        output_plot: str = "",
    ) -> dict[str, Any]:
        path = require_file(history_file)
        data = parse_residual_table(path)
        independent = "iteration" if "iteration" in data else next(iter(data))
        series = {name: values for name, values in data.items() if name != independent}
        summaries = {name: summarize_series(values) for name, values in series.items()}
        plot_path = ""
        if output_plot:
            plot_path = plot_history(data, independent, output_plot)
        return {
            "history_file": str(path),
            "independent_column": independent,
            "rows": len(data.get(independent, [])),
            "series_names": list(series),
            "summaries": summaries,
            "output_plot": plot_path,
        }
