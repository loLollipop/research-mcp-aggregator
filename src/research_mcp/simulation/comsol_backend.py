"""Local COMSOL backend ported from upstream comsol-mcp (MPh-based).

The upstream repository ``comsol-mcp`` by mr jiang (MIT license, Tsinghua)
connects to a running COMSOL Multiphysics Server through the MPh library.
We extract the core connection / model / parameter / solve lifecycle without
running its MCP server or duplicating its global state machinery.
"""

from __future__ import annotations

import importlib
import importlib.metadata
import importlib.util
import logging
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as _FutureTimeout
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

logger = logging.getLogger("research-mcp.comsol")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_DEFAULT_TIMEOUT_S = 30.0
_DEFAULT_DISCONNECT_TIMEOUT_S = 15.0


@dataclass(frozen=True)
class ComsolServerConfig:
    """Configuration for connecting to a COMSOL Multiphysics Server."""

    host: str = "localhost"
    port: int = 2036
    connect_timeout_s: float = 30.0
    model_path: str = ""


# ---------------------------------------------------------------------------
# Backend
# ---------------------------------------------------------------------------


class ComsolBackend:
    """In-process COMSOL MPh backend for local research-mcp tools.

    One ``ComsolBackend`` instance owns at most one live MPh session at a
    time (matching upstream ``comsol-mcp`` design).
    """

    def __init__(self) -> None:
        self._client: Any = None
        self._connected: bool = False
        self._host: str = ""
        self._port: int = 0
        self._model: Any = None
        self._model_path: str = ""
        self._model_label: str = ""
        self._jobs: dict[str, dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # MPh availability
    # ------------------------------------------------------------------

    def check_mph(self) -> dict[str, Any]:
        """Check whether the MPh library appears available without importing it.

        Importing ``mph`` can initialize JPype/COMSOL discovery and block in lightweight
        MCP smoke checks, so availability probing must stay metadata-only.
        """
        try:
            available = importlib.util.find_spec("mph") is not None
        except (ImportError, ModuleNotFoundError, ValueError):
            available = False

        if not available:
            return {
                "status": "not_found",
                "module": "mph",
                "action": "Install MPh: pip install MPh",
            }

        try:
            version = importlib.metadata.version("MPh")
        except importlib.metadata.PackageNotFoundError:
            version = "unknown"

        return {
            "status": "available",
            "module": "mph",
            "version": version,
            "connected": self._connected,
            "host": self._host,
            "port": self._port,
            "model_label": self._model_label,
        }

    # ------------------------------------------------------------------
    # Server connection
    # ------------------------------------------------------------------

    def server_connect(self, config: ComsolServerConfig) -> dict[str, Any]:
        """Connect to an already running COMSOL Multiphysics Server.

        This is the *attach-first* pattern from upstream ``comsol-mcp``:
        the user manually starts COMSOL Server, and MCP attaches to it.
        """
        try:
            mph = importlib.import_module("mph")
        except ImportError:
            return {
                "status": "not_found",
                "module": "mph",
                "action": "Install MPh and ensure COMSOL Server is running.",
            }

        if self._connected and self._client is not None:
            self._disconnect_internal()

        host = config.host or "localhost"
        port = int(config.port)

        def _connect() -> Any:
            client = mph.Client(host=None)
            client.connect(port, host)
            return client

        try:
            self._client = self._timed_call(
                _connect,
                timeout=max(5.0, config.connect_timeout_s),
                error_msg=(
                    f"Connection to {host}:{port} timed out after "
                    f"{config.connect_timeout_s}s. "
                    "Ensure COMSOL Multiphysics Server is running and the port is correct."
                ),
            )
        except RuntimeError as exc:
            return {
                "status": "error",
                "connected": False,
                "host": host,
                "port": port,
                "message": str(exc),
            }

        self._connected = True
        self._host = host
        self._port = port

        result: dict[str, Any] = {
            "status": "ok",
            "connected": True,
            "host": host,
            "port": port,
        }

        # Auto-load model if path provided
        if config.model_path:
            load_result = self.model_load(config.model_path)
            result["model"] = load_result

        return result

    def server_disconnect(self) -> dict[str, Any]:
        """Disconnect from the COMSOL Server and release resources."""
        if not self._connected:
            return {"status": "ok", "connected": False, "message": "Already disconnected."}

        self._disconnect_internal()
        return {"status": "ok", "connected": False}

    def server_info(self) -> dict[str, Any]:
        """Return current connection and model status."""
        return {
            "status": "ok",
            "connected": self._connected,
            "host": self._host,
            "port": self._port,
            "model_label": self._model_label,
            "model_path": self._model_path,
            "jobs": list(self._jobs),
        }

    # ------------------------------------------------------------------
    # Model lifecycle
    # ------------------------------------------------------------------

    def model_load(self, model_path: str) -> dict[str, Any]:
        """Load a ``.mph`` model file on the connected server."""
        if not self._connected or self._client is None:
            return {
                "status": "not_connected",
                "action": "Call server_connect first.",
            }

        path = Path(model_path).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"Model not found: {path}")

        try:
            self._model = self._client.load(path)
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

        self._model_path = str(path)
        self._model_label = path.stem
        return {
            "status": "ok",
            "model_label": self._model_label,
            "model_path": self._model_path,
        }

    def model_create(self, name: str = "Server Model") -> dict[str, Any]:
        """Create a new empty model on the connected server."""
        if not self._connected or self._client is None:
            return {"status": "not_connected", "action": "Call server_connect first."}

        try:
            self._model = self._client.create(name or "Server Model")
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

        self._model_path = ""
        self._model_label = name or "Server Model"
        return {
            "status": "ok",
            "model_label": self._model_label,
        }

    def model_save(self, save_path: str = "") -> dict[str, Any]:
        """Save the current model."""
        if self._model is None:
            return {"status": "no_model", "action": "Load or create a model first."}

        target = save_path or self._model_path
        if not target:
            return {
                "status": "error",
                "message": "No save path provided and model has no file path.",
            }

        resolved = str(Path(target).expanduser().resolve())
        try:
            self._model.save(resolved)
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

        self._model_path = resolved
        return {"status": "ok", "model_path": resolved}

    # ------------------------------------------------------------------
    # Parameter operations
    # ------------------------------------------------------------------

    def get_parameters(self) -> dict[str, Any]:
        """Return global parameters from the current model."""
        if self._model is None:
            return {"status": "no_model", "action": "Load a model first."}

        try:
            names = list(self._model.java.param().varnames())
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

        rows: list[dict[str, str]] = []
        for name in names:
            key = str(name)
            try:
                expr = str(self._model.java.param().get(key))
            except Exception:
                expr = ""
            rows.append({"name": key, "expression": expr})

        return {
            "status": "ok",
            "model_label": self._model_label,
            "parameters": rows,
            "count": len(rows),
        }

    def set_parameters(self, parameters: list[dict[str, str]]) -> dict[str, Any]:
        """Set global parameters on the current model.

        Each item: ``{"name": "...", "expression": "..."}``
        """
        if self._model is None:
            return {"status": "no_model", "action": "Load a model first."}

        updated: list[dict[str, str]] = []
        for item in parameters:
            name = str(item.get("name", "")).strip()
            expression = str(item.get("expression", "")).strip()
            if not name:
                raise ValueError("Parameter name is required.")
            if not expression:
                raise ValueError(f"Expression is required for parameter '{name}'.")
            try:
                self._model.java.param().set(name, expression)
            except Exception as exc:
                return {"status": "error", "message": str(exc), "updated": updated}
            updated.append({"name": name, "expression": expression})

        return {"status": "ok", "updated": updated, "count": len(updated)}

    def evaluate_expression(self, expression: str) -> dict[str, Any]:
        """Evaluate a single expression on the current model."""
        if self._model is None:
            return {"status": "no_model", "action": "Load a model first."}

        try:
            raw = self._model.evaluate(expression.strip())
        except Exception as exc:
            return {"status": "error", "expression": expression, "message": str(exc)}

        value = self._coerce_value(raw)
        return {
            "status": "ok",
            "expression": expression,
            "value": value,
        }

    # ------------------------------------------------------------------
    # Solve
    # ------------------------------------------------------------------

    def solve(self, study_tag: str = "") -> dict[str, Any]:
        """Solve the current model, optionally for a specific study tag."""
        if self._model is None:
            return {"status": "no_model", "action": "Load a model first."}

        try:
            if study_tag:
                try:
                    label = str(self._model.java.study().get(study_tag).label())
                    self._model.solve(label)
                except Exception:
                    self._model.solve(study_tag)
            else:
                self._model.solve()
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

        return {
            "status": "ok",
            "study_tag": study_tag or "(default)",
            "model_label": self._model_label,
        }

    def solve_async(self, study_tag: str = "") -> dict[str, Any]:
        """Start a solve in a background thread; return a job_id for polling."""
        if self._model is None:
            return {"status": "no_model", "action": "Load a model first."}

        job_id = uuid4().hex[:8]
        self._jobs[job_id] = {
            "job_id": job_id,
            "status": "running",
            "study_tag": study_tag or "(default)",
            "model_label": self._model_label,
            "result": None,
            "error": None,
        }

        import threading

        def _worker() -> None:
            try:
                if study_tag:
                    try:
                        label = str(self._model.java.study().get(study_tag).label())
                        self._model.solve(label)
                    except Exception:
                        self._model.solve(study_tag)
                else:
                    self._model.solve()
                self._jobs[job_id].update(status="succeeded", result={"study_tag": study_tag})
            except Exception as exc:
                logger.exception("Background solve %s failed", job_id)
                self._jobs[job_id].update(status="failed", error=str(exc))

        thread = threading.Thread(target=_worker, name=f"comsol-solve-{job_id}", daemon=True)
        thread.start()
        return {
            "status": "ok",
            "job_id": job_id,
            "study_tag": study_tag or "(default)",
            "message": "Solve started in background. Call comsol_solve_status to poll.",
        }

    def solve_status(self, job_id: str = "") -> dict[str, Any]:
        """Poll the status of a background solve job."""
        if not self._jobs:
            return {"status": "no_jobs", "message": "No solve jobs have been started."}

        if job_id:
            job = self._jobs.get(job_id)
            if job is None:
                return {"status": "not_found", "job_id": job_id}
            return {"status": "ok", "job": job}

        # Return the latest job
        latest_id = next(reversed(self._jobs))
        return {"status": "ok", "job": self._jobs[latest_id]}

    # ------------------------------------------------------------------
    # Study listing
    # ------------------------------------------------------------------

    def list_studies(self) -> dict[str, Any]:
        """List study tags in the current model."""
        if self._model is None:
            return {"status": "no_model", "action": "Load a model first."}

        try:
            tags = [str(t) for t in self._model.java.study().tags()]
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

        return {
            "status": "ok",
            "model_label": self._model_label,
            "studies": tags,
            "count": len(tags),
        }

    def list_solver_configs(self) -> dict[str, Any]:
        """List solver configurations (sol tags) in the current model."""
        if self._model is None:
            return {"status": "no_model", "action": "Load a model first."}

        try:
            tags = [str(t) for t in self._model.java.sol().tags()]
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

        return {
            "status": "ok",
            "model_label": self._model_label,
            "solver_configs": tags,
            "count": len(tags),
        }

    # ------------------------------------------------------------------
    # File inspection
    # ------------------------------------------------------------------

    def inspect_file(self, file_path: str, preview_chars: int = 1000) -> dict[str, Any]:
        """Inspect a COMSOL-related file for metadata and optional preview."""
        path = Path(file_path).expanduser().resolve()
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(f"File not found: {path}")

        suffix = path.suffix.lower()
        file_type = {
            ".mph": "COMSOL model file",
            ".java": "COMSOL Java file",
            ".m": "COMSOL MATLAB file",
            ".csv": "COMSOL exported table",
            ".txt": "COMSOL text output",
            ".dat": "COMSOL data file",
        }.get(suffix, f"File ({suffix})")

        info: dict[str, Any] = {
            "path": str(path),
            "name": path.name,
            "size_bytes": path.stat().st_size,
            "extension": suffix,
            "type": file_type,
        }

        if suffix in {".csv", ".txt", ".java", ".m"}:
            info["preview"] = path.read_text(encoding="utf-8", errors="ignore")[:preview_chars]

        return {"status": "ok", "file_info": info}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _disconnect_internal(self) -> None:
        """Disconnect from server without returning a result dict."""
        if self._client is not None:
            try:
                self._timed_call(
                    self._client.disconnect,
                    timeout=_DEFAULT_DISCONNECT_TIMEOUT_S,
                    error_msg="Disconnect timed out",
                )
            except Exception as exc:
                if "not connected" not in str(exc).lower():
                    logger.debug("Disconnect error: %s", exc)
            finally:
                self._client = None
                self._connected = False
                self._model = None
                self._model_path = ""
                self._model_label = ""
                self._host = ""
                self._port = 0
        else:
            self._connected = False

    @staticmethod
    def _timed_call(func: Any, *args: Any, timeout: float = 30.0, error_msg: str = "") -> Any:
        """Run *func* in a daemon thread with a hard timeout.

        Uses ``shutdown(wait=False)`` so a hung Java call never blocks
        the caller; the worker thread is a daemon and will not prevent
        process exit.
        """
        executor = ThreadPoolExecutor(max_workers=1)
        try:
            future = executor.submit(func, *args)
            return future.result(timeout=timeout)
        except _FutureTimeout:
            raise RuntimeError(error_msg or f"Operation timed out after {timeout}s")
        finally:
            executor.shutdown(wait=False)

    @staticmethod
    def _coerce_value(value: Any) -> Any:
        """Coerce MPh / Java return values into JSON-safe Python types."""
        if hasattr(value, "tolist"):
            try:
                return value.tolist()
            except Exception:
                pass
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        if isinstance(value, (list, tuple)):
            return [ComsolBackend._coerce_value(item) for item in value]
        return str(value)
