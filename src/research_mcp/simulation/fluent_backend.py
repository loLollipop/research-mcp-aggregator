"""Local PyFluent backend ported from upstream ANSYS MCP semantics."""

from __future__ import annotations

import importlib
import importlib.metadata
import importlib.util
import inspect
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4


@dataclass(frozen=True)
class FluentSessionConfig:
    """Configuration for launching an Ansys Fluent solver session."""

    precision: str = "double"
    dimension: str = "3d"
    mode: str = "solver"
    processor_count: int = 1
    working_directory: str = ""
    fluent_path: str = ""


class FluentBackend:
    """In-process PyFluent backend for local research-mcp tools."""

    def __init__(self) -> None:
        self._sessions: dict[str, Any] = {}

    def check_pyfluent(self) -> dict[str, Any]:
        """Check PyFluent availability without importing the heavy runtime module."""
        try:
            available = importlib.util.find_spec("ansys.fluent.core") is not None
        except (ImportError, ModuleNotFoundError, ValueError):
            available = False

        if not available:
            return {
                "status": "not_found",
                "module": "ansys.fluent.core",
                "action": "Install the simulation extra with ansys-fluent-core available.",
            }

        try:
            version = importlib.metadata.version("ansys-fluent-core")
        except importlib.metadata.PackageNotFoundError:
            version = "unknown"

        return {
            "status": "available",
            "module": "ansys.fluent.core",
            "version": version,
            "ansys_root": os.environ.get("ANSYS_ROOT", ""),
            "active_sessions": sorted(self._sessions),
        }

    def launch_session(self, config: FluentSessionConfig) -> dict[str, Any]:
        try:
            pyfluent = importlib.import_module("ansys.fluent.core")
        except ImportError:
            return {
                "status": "not_found",
                "module": "ansys.fluent.core",
                "action": "Install ansys-fluent-core and ensure Fluent licensing is configured.",
            }

        if config.precision not in {"single", "double"}:
            raise ValueError("precision must be 'single' or 'double'")
        if config.dimension not in {"2d", "3d"}:
            raise ValueError("dimension must be '2d' or '3d'")
        if config.processor_count < 1:
            raise ValueError("processor_count must be >= 1")

        launch_parameters = inspect.signature(pyfluent.launch_fluent).parameters
        launch_kwargs: dict[str, Any] = {
            "precision": config.precision,
            "mode": config.mode,
        }
        if _launch_has_parameter(launch_parameters, "dimension"):
            launch_kwargs["dimension"] = 2 if config.dimension == "2d" else 3
        elif _launch_has_parameter(launch_parameters, "version"):
            launch_kwargs["version"] = config.dimension
        if _launch_has_parameter(launch_parameters, "processor_count"):
            launch_kwargs["processor_count"] = config.processor_count

        fluent_root_override: str | None = None
        if config.working_directory:
            working_directory = Path(config.working_directory).expanduser().resolve()
            if not working_directory.exists() or not working_directory.is_dir():
                raise FileNotFoundError(f"Working directory not found: {working_directory}")
            launch_kwargs["cwd"] = str(working_directory)
        if config.fluent_path:
            fluent_path = Path(config.fluent_path).expanduser().resolve()
            if not fluent_path.exists() or not fluent_path.is_file():
                raise FileNotFoundError(f"Fluent executable not found: {fluent_path}")
            if _launch_has_parameter(launch_parameters, "fluent_path"):
                launch_kwargs["fluent_path"] = str(fluent_path)
            else:
                fluent_root_override = str(_infer_fluent_root(fluent_path))

        try:
            old_fluent_root = os.environ.get("PYFLUENT_FLUENT_ROOT")
            if fluent_root_override:
                os.environ["PYFLUENT_FLUENT_ROOT"] = fluent_root_override
            try:
                session = pyfluent.launch_fluent(**launch_kwargs)
            finally:
                if fluent_root_override:
                    if old_fluent_root is None:
                        os.environ.pop("PYFLUENT_FLUENT_ROOT", None)
                    else:
                        os.environ["PYFLUENT_FLUENT_ROOT"] = old_fluent_root
        except Exception as exc:
            debug_kwargs = dict(launch_kwargs)
            if fluent_root_override:
                debug_kwargs["fluent_root"] = fluent_root_override
            return {"status": "error", "message": str(exc), "launch_kwargs": debug_kwargs}

        session_id = uuid4().hex[:8]
        self._sessions[session_id] = session
        return {
            "status": "ok",
            "session_id": session_id,
            "precision": config.precision,
            "dimension": config.dimension,
            "mode": config.mode,
            "processor_count": config.processor_count,
            "working_directory": launch_kwargs.get("cwd", ""),
        }

    def inspect_file(self, file_path: str, preview_chars: int = 1000) -> dict[str, Any]:
        path = Path(file_path).expanduser().resolve()
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(f"File not found: {path}")

        name = path.name.lower()
        suffix = path.suffix.lower()
        extension = next(
            (ext for ext in (".cas.h5", ".dat.h5", ".cas", ".dat", ".jou") if name.endswith(ext)),
            suffix,
        )
        file_type = {
            ".cas": "Fluent case file",
            ".cas.h5": "Fluent case file",
            ".dat": "Fluent data file",
            ".dat.h5": "Fluent data file",
            ".jou": "Fluent journal file",
        }.get(extension, "Unknown Fluent file")

        info: dict[str, Any] = {
            "path": str(path),
            "name": path.name,
            "size_bytes": path.stat().st_size,
            "extension": extension,
            "type": file_type,
        }
        if extension == ".jou":
            info["preview"] = path.read_text(encoding="utf-8", errors="ignore")[:preview_chars]
        return {"status": "ok", "file_info": info}

    def list_sessions(self) -> dict[str, Any]:
        return {"status": "ok", "sessions": sorted(self._sessions), "count": len(self._sessions)}

    def execute_tui(self, session_id: str, commands: list[str]) -> dict[str, Any]:
        session = self._sessions.get(session_id)
        if session is None:
            return {
                "status": "not_found",
                "session_id": session_id,
                "action": "Launch a Fluent session first.",
            }

        results: list[dict[str, Any]] = []
        for command in commands:
            stripped = command.strip()
            if not stripped or stripped.startswith("#"):
                continue
            try:
                output = session.tui.execute_command(stripped)
            except Exception as exc:
                return {
                    "status": "error",
                    "session_id": session_id,
                    "command": stripped,
                    "message": str(exc),
                    "results": results,
                }
            results.append({"command": stripped, "output": output})
        return {
            "status": "ok",
            "session_id": session_id,
            "commands_executed": len(results),
            "results": results,
        }

    def close_session(self, session_id: str) -> dict[str, Any]:
        session = self._sessions.pop(session_id, None)
        if session is None:
            return {"status": "not_found", "session_id": session_id}

        exit_method = getattr(session, "exit", None) or getattr(session, "quit", None)
        if callable(exit_method):
            exit_method()
        return {"status": "ok", "session_id": session_id, "closed": True}

    def close_all_sessions(self) -> dict[str, Any]:
        """Close every tracked Fluent session during adapter shutdown."""
        session_ids = list(self._sessions)
        closed: list[str] = []
        errors: dict[str, str] = {}
        for session_id in session_ids:
            try:
                result = self.close_session(session_id)
                if result.get("closed"):
                    closed.append(session_id)
            except Exception as exc:
                self._sessions.pop(session_id, None)
                errors[session_id] = str(exc)
        return {
            "status": "ok" if not errors else "partial",
            "closed": closed,
            "errors": errors,
        }


def _infer_fluent_root(fluent_executable: Path) -> Path:
    """Infer the Fluent root folder from a Fluent executable path."""
    if fluent_executable.parent.name.lower() == "win64":
        ntbin = fluent_executable.parent.parent
        if ntbin.name.lower() == "ntbin":
            return ntbin.parent
    return fluent_executable.parent


def _launch_has_parameter(
    parameters: inspect.Signature.parameters, parameter_name: str
) -> bool:
    """Return whether launch_fluent explicitly supports a keyword.

    PyFluent 0.15 exposes ``**kwargs`` but raises for unknown keys at runtime,
    so only explicitly declared parameters are treated as supported.
    """
    return parameter_name in parameters
