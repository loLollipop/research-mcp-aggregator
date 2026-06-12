"""OriginLab Origin adapter for local plotting and analysis workflows.

This adapter intentionally keeps Origin as an optional Windows-only runtime
capability. Importing the adapter must not require Origin, ``originpro``, or
``pywin32`` so the main research-mcp server remains portable.
"""

from __future__ import annotations

import importlib
import importlib.util
import os
import platform
import re
import threading
from contextlib import suppress
from pathlib import Path
from typing import Any, Callable, TypeVar

from research_mcp.adapters import AdapterMeta, BaseAdapter, ToolSpec, register_adapter

ORIGIN_PROJECT_SUFFIXES = {".opj", ".opju"}
ORIGIN_TABLE_SUFFIXES = {".csv", ".dat", ".txt", ".tsv"}
ORIGIN_FIGURE_SUFFIXES = {".eps", ".jpg", ".jpeg", ".pdf", ".png", ".svg", ".tif", ".tiff"}

PLOT_TYPE_TO_TEMPLATE = {
    "line": "line",
    "scatter": "scatter",
    "line_symbol": "linesymb",
    "line+symbol": "linesymb",
    "column": "column",
    "area": "area",
}

DANGEROUS_LABTALK_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bdoc\s*-\s*[sr]\b",
        r"\bnewbook\s*-\s*d\b",
        r"\bwin(?:dow)?\s*-\s*c?d\b",
        r"\bdel(?:ete)?\b",
        r"\berase\b",
        r"\bexpgraph\b",
        r"\bopen\b",
        r"\bsave(?:as)?\b",
        r"\brun(?:\.|\s|-)",
        r"\bsystem\b",
    )
]

T = TypeVar("T")


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


def _module_available(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def _success(
    message: str,
    data: dict[str, Any] | None = None,
    warnings: list[str] | None = None,
    next_suggestions: list[str] | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {"status": "ok", "message": message}
    if data is not None:
        result["data"] = data
    if warnings:
        result["warnings"] = warnings
    if next_suggestions:
        result["next_suggestions"] = next_suggestions
    return result


def _error(
    message: str,
    error_type: str = "origin_error",
    target: str | None = None,
    value: Any | None = None,
    hint: str | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "status": "error",
        "error_type": error_type,
        "message": message,
    }
    if target is not None:
        result["target"] = target
    if value is not None:
        result["value"] = value
    if hint:
        result["hint"] = hint
    return result


def _quote_labtalk_text(text: str) -> str:
    return text.replace('"', '\\"')


@register_adapter
class OriginAdapter(BaseAdapter):
    """Expose local OriginLab Origin/OriginPro workflows to MCP clients."""

    adapter_name = "origin"

    def __init__(self) -> None:
        self.origin_exe = os.getenv("ORIGIN_EXE") or self._detect_origin_exe()
        self.visible = _env_bool("ORIGIN_VISIBLE", True)
        self._lock = threading.Lock()
        self._op: Any | None = None
        self._connected = False
        self._active_worksheet: str | None = None
        self._active_graph: str | None = None

    def metadata(self) -> AdapterMeta:
        return AdapterMeta(
            name="origin",
            description=(
                "Local OriginLab Origin/OriginPro tools using optional originpro/COM "
                "automation for worksheets, graphs, styling, export, and LabTalk."
            ),
            tools=[
                ToolSpec(
                    name="origin_check_config",
                    description="Check local Origin installation and optional Python dependencies.",
                    input_schema={"type": "object", "properties": {}},
                    handler=self.check_config,
                ),
                ToolSpec(
                    name="origin_get_info",
                    description="Connect to Origin and return version, path, and open page summary.",
                    input_schema={"type": "object", "properties": {}},
                    handler=self.get_info,
                ),
                ToolSpec(
                    name="origin_new_project",
                    description="Create a new empty Origin project.",
                    input_schema={"type": "object", "properties": {}},
                    handler=self.new_project,
                ),
                ToolSpec(
                    name="origin_open_project",
                    description="Open an existing Origin .opj/.opju project.",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "file_path": {"type": "string", "minLength": 1},
                            "readonly": {"type": "boolean", "default": False},
                        },
                        "required": ["file_path"],
                    },
                    handler=self.open_project,
                ),
                ToolSpec(
                    name="origin_save_project",
                    description="Save the current Origin project to .opj/.opju.",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "file_path": {
                                "type": "string",
                                "description": "Optional output .opj/.opju path.",
                            }
                        },
                    },
                    handler=self.save_project,
                ),
                ToolSpec(
                    name="origin_import_csv",
                    description="Import a local CSV/TXT/TSV/DAT file into an Origin worksheet.",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "file_path": {"type": "string", "minLength": 1},
                            "sheet_name": {
                                "type": "string",
                                "description": "Optional target worksheet long name.",
                            },
                        },
                        "required": ["file_path"],
                    },
                    handler=self.import_csv,
                ),
                ToolSpec(
                    name="origin_list_worksheets",
                    description="List Origin workbook pages and worksheet metadata.",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "preview_rows": {
                                "type": "integer",
                                "default": 0,
                                "minimum": 0,
                                "maximum": 20,
                            }
                        },
                    },
                    handler=self.list_worksheets,
                ),
                ToolSpec(
                    name="origin_create_plot",
                    description=(
                        "Create an Origin graph from worksheet columns. Column indices are "
                        "0-based, matching originpro."
                    ),
                    input_schema={
                        "type": "object",
                        "properties": {
                            "x_col": {"type": "integer", "minimum": 0},
                            "y_cols": {
                                "anyOf": [
                                    {"type": "integer", "minimum": 0},
                                    {
                                        "type": "array",
                                        "items": {"type": "integer", "minimum": 0},
                                        "minItems": 1,
                                        "maxItems": 64,
                                    },
                                ]
                            },
                            "sheet_name": {
                                "type": "string",
                                "description": "Optional worksheet name; defaults to active worksheet.",
                            },
                            "plot_type": {
                                "type": "string",
                                "enum": list(PLOT_TYPE_TO_TEMPLATE),
                                "default": "line",
                            },
                            "graph_name": {
                                "type": "string",
                                "description": "Optional requested graph page name.",
                            },
                        },
                        "required": ["x_col", "y_cols"],
                    },
                    handler=self.create_plot,
                ),
                ToolSpec(
                    name="origin_apply_publication_style",
                    description="Apply basic publication-style labels, font, legend refresh, and rescale.",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "graph_name": {
                                "type": "string",
                                "description": "Optional graph name; defaults to active graph.",
                            },
                            "x_label": {"type": "string"},
                            "y_label": {"type": "string"},
                            "title": {"type": "string"},
                            "font": {"type": "string", "default": "Arial"},
                            "refresh_legend": {"type": "boolean", "default": True},
                            "rescale": {"type": "boolean", "default": True},
                        },
                    },
                    handler=self.apply_publication_style,
                ),
                ToolSpec(
                    name="origin_export_graph",
                    description="Export an Origin graph to PNG/SVG/PDF/TIF/JPG/EPS.",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "output_path": {"type": "string", "minLength": 1},
                            "graph_name": {
                                "type": "string",
                                "description": "Optional graph name; defaults to active graph.",
                            },
                            "output_format": {
                                "type": "string",
                                "description": "Optional format override; otherwise inferred from suffix.",
                            },
                            "width": {
                                "type": "integer",
                                "default": 1200,
                                "minimum": 100,
                                "maximum": 10000,
                            },
                        },
                        "required": ["output_path"],
                    },
                    handler=self.export_graph,
                ),
                ToolSpec(
                    name="origin_execute_labtalk",
                    description=(
                        "Execute a non-destructive LabTalk command for advanced graph tweaks. "
                        "Typed tools should be preferred for import/export/project operations."
                    ),
                    input_schema={
                        "type": "object",
                        "properties": {
                            "command": {"type": "string", "minLength": 1, "maxLength": 2000}
                        },
                        "required": ["command"],
                    },
                    handler=self.execute_labtalk,
                ),
                ToolSpec(
                    name="origin_release",
                    description="Release Origin COM control while keeping Origin open for manual use.",
                    input_schema={"type": "object", "properties": {}},
                    handler=self.release,
                ),
            ],
        )

    async def initialize(self, config: dict[str, Any] | None = None) -> None:
        config = config or {}
        self.origin_exe = str(config.get("origin_exe") or os.getenv("ORIGIN_EXE") or self.origin_exe)
        if "visible" in config:
            self.visible = bool(config["visible"])

    async def shutdown(self) -> None:
        await self.release()

    async def check_config(self) -> dict[str, Any]:
        installations = self._find_origin_installations()
        origin_exe_path = Path(self.origin_exe).expanduser() if self.origin_exe else None
        origin_exe_exists = bool(origin_exe_path and origin_exe_path.exists())
        data = {
            "notice": (
                "Origin tools control an existing local Origin/OriginPro installation; "
                "they do not replace Origin licensing or expert figure review."
            ),
            "platform": platform.platform(),
            "origin_exe": self.origin_exe,
            "origin_exe_exists": origin_exe_exists,
            "origin_visible": self.visible,
            "originpro_available": _module_available("originpro"),
            "pywin32_available": _module_available("win32com"),
            "detected_installations": installations,
            "connected": self._connected,
            "active_worksheet": self._active_worksheet,
            "active_graph": self._active_graph,
        }
        warnings: list[str] = []
        if platform.system() != "Windows":
            warnings.append("Origin COM automation is Windows-only.")
        if not data["originpro_available"]:
            warnings.append("Python package 'originpro' is not available in this environment.")
        if not data["pywin32_available"]:
            warnings.append("Python package 'pywin32' is not available in this environment.")
        if not installations and not origin_exe_exists:
            warnings.append("No Origin installation was detected from the registry or ORIGIN_EXE.")
        return _success("Origin configuration checked.", data=data, warnings=warnings)

    async def get_info(self) -> dict[str, Any]:
        try:
            data = self._execute(self._collect_origin_info)
        except Exception as exc:
            return _error(
                f"Could not connect to Origin: {exc}",
                error_type="origin_unavailable",
                hint="Install research-mcp[origin], ensure Origin is licensed, and run on Windows Python.",
            )
        return _success("Origin connection information collected.", data=data)

    async def new_project(self) -> dict[str, Any]:
        def _new(op: Any) -> dict[str, Any]:
            if not hasattr(op, "new"):
                raise RuntimeError("originpro.new() is not available in this Origin Python API.")
            op.new()
            self._active_worksheet = None
            self._active_graph = None
            return {"connected": True}

        try:
            data = self._execute(_new)
        except Exception as exc:
            return _error(f"Could not create a new Origin project: {exc}")
        return _success("New Origin project created.", data=data)

    async def open_project(self, file_path: str, readonly: bool = False) -> dict[str, Any]:
        path, err = self._resolve_existing_file(file_path, ORIGIN_PROJECT_SUFFIXES)
        if err:
            return err

        def _open(op: Any) -> dict[str, Any]:
            try:
                op.open(str(path), readonly=readonly)
            except TypeError:
                op.open(str(path))
            self._refresh_active_context_unlocked(op)
            return {"file_path": str(path), "readonly": readonly}

        try:
            data = self._execute(_open)
        except Exception as exc:
            return _error(f"Could not open Origin project: {exc}")
        return _success("Origin project opened.", data=data)

    async def save_project(self, file_path: str = "") -> dict[str, Any]:
        path: Path | None = None
        if file_path:
            path, err = self._resolve_output_path(file_path, ORIGIN_PROJECT_SUFFIXES)
            if err:
                return err

        def _save(op: Any) -> dict[str, Any]:
            if path is None:
                op.save()
                return {"file_path": "current project"}
            op.save(str(path))
            return {"file_path": str(path)}

        try:
            data = self._execute(_save)
        except Exception as exc:
            return _error(f"Could not save Origin project: {exc}")
        return _success("Origin project saved.", data=data)

    async def import_csv(self, file_path: str, sheet_name: str = "") -> dict[str, Any]:
        path, err = self._resolve_existing_file(file_path, ORIGIN_TABLE_SUFFIXES)
        if err:
            return err

        def _import(op: Any) -> dict[str, Any]:
            wks = op.find_sheet("w", sheet_name) if sheet_name else None
            if wks is None:
                wks = op.new_sheet(lname=sheet_name or None)
            wks.from_file(str(path))
            full_name = self._worksheet_full_name(wks)
            self._active_worksheet = full_name
            return {
                "source_file": str(path),
                "sheet_name": full_name,
                "rows": getattr(wks, "rows", None),
                "columns": getattr(wks, "cols", None),
            }

        try:
            data = self._execute(_import)
        except Exception as exc:
            return _error(f"Could not import data into Origin: {exc}")
        return _success(
            "CSV/text data imported into Origin.",
            data=data,
            next_suggestions=["origin_list_worksheets", "origin_create_plot"],
        )

    async def list_worksheets(self, preview_rows: int = 0) -> dict[str, Any]:
        def _list(op: Any) -> dict[str, Any]:
            workbooks: list[dict[str, Any]] = []
            for book in self._iter_pages(op, "Book"):
                book_info: dict[str, Any] = {
                    "name": getattr(book, "name", str(book)),
                    "worksheets": [],
                }
                for wks in self._iter_book_sheets(book):
                    sheet_info = self._worksheet_info(wks, preview_rows)
                    book_info["worksheets"].append(sheet_info)
                workbooks.append(book_info)
            self._refresh_active_context_unlocked(op)
            return {
                "workbook_count": len(workbooks),
                "workbooks": workbooks,
                "active_worksheet": self._active_worksheet,
                "active_graph": self._active_graph,
            }

        try:
            data = self._execute(_list)
        except Exception as exc:
            return _error(f"Could not list Origin worksheets: {exc}")
        return _success("Origin worksheets listed.", data=data)

    async def create_plot(
        self,
        x_col: int,
        y_cols: int | list[int],
        sheet_name: str = "",
        plot_type: str = "line",
        graph_name: str = "",
    ) -> dict[str, Any]:
        if plot_type not in PLOT_TYPE_TO_TEMPLATE:
            return _error(
                f"Unsupported plot_type: {plot_type}",
                error_type="unsupported",
                target="plot_type",
                value=plot_type,
                hint=f"Supported plot types: {', '.join(PLOT_TYPE_TO_TEMPLATE)}",
            )
        y_col_list = [y_cols] if isinstance(y_cols, int) else list(y_cols)
        if not y_col_list:
            return _error("y_cols must contain at least one Y column.", target="y_cols")

        def _plot(op: Any) -> dict[str, Any]:
            wks = self._find_worksheet(op, sheet_name)
            total_cols = getattr(wks, "cols", 0)
            self._validate_column_indices([x_col, *y_col_list], total_cols)
            graph = op.new_graph(template=PLOT_TYPE_TO_TEMPLATE[plot_type])
            if graph_name:
                with suppress(Exception):
                    graph.name = graph_name
            layer = self._get_graph_layer(graph, 0)
            curves: list[dict[str, int]] = []
            for index, y_col in enumerate(y_col_list):
                layer.add_plot(wks, coly=y_col, colx=x_col)
                curves.append({"plot_index": index, "x_col": x_col, "y_col": y_col})
            with suppress(Exception):
                layer.rescale()
            with suppress(Exception):
                layer.group()
            actual_graph_name = getattr(graph, "name", graph_name or "")
            self._active_graph = actual_graph_name
            self._active_worksheet = self._worksheet_full_name(wks)
            return {
                "graph_name": actual_graph_name,
                "sheet_name": self._active_worksheet,
                "plot_type": plot_type,
                "curve_count": len(curves),
                "curves": curves,
            }

        try:
            data = self._execute(_plot)
        except Exception as exc:
            return _error(f"Could not create Origin graph: {exc}")
        return _success(
            "Origin graph created.",
            data=data,
            next_suggestions=["origin_apply_publication_style", "origin_export_graph"],
        )

    async def apply_publication_style(
        self,
        graph_name: str = "",
        x_label: str = "",
        y_label: str = "",
        title: str = "",
        font: str = "Arial",
        refresh_legend: bool = True,
        rescale: bool = True,
    ) -> dict[str, Any]:
        def _style(op: Any) -> dict[str, Any]:
            graph = self._find_graph(op, graph_name)
            target_graph = getattr(graph, "name", graph_name or self._active_graph or "")
            op.lt_exec(f"win -a {target_graph};")
            commands: list[str] = []
            if font:
                commands.append(f'page.font$="{_quote_labtalk_text(font)}";')
            if x_label:
                commands.append(f'xb.text$="{_quote_labtalk_text(x_label)}";')
            if y_label:
                commands.append(f'yl.text$="{_quote_labtalk_text(y_label)}";')
            if title:
                commands.append(f'page.title$="{_quote_labtalk_text(title)}";')
            if refresh_legend:
                commands.append("legend -r;")
            if rescale:
                commands.append("layer -a;")
            for command in commands:
                op.lt_exec(command)
            self._active_graph = target_graph
            return {"graph_name": target_graph, "commands_executed": commands}

        try:
            data = self._execute(_style)
        except Exception as exc:
            return _error(f"Could not apply Origin graph styling: {exc}")
        return _success(
            "Basic publication style applied to Origin graph.",
            data=data,
            warnings=[
                "This first-party adapter applies a conservative style subset. "
                "Use origin_execute_labtalk for advanced Origin-specific styling."
            ],
            next_suggestions=["origin_export_graph", "origin_save_project"],
        )

    async def export_graph(
        self,
        output_path: str,
        graph_name: str = "",
        output_format: str = "",
        width: int = 1200,
    ) -> dict[str, Any]:
        path, err = self._resolve_output_path(output_path, ORIGIN_FIGURE_SUFFIXES)
        if err:
            return err
        fmt = (output_format or path.suffix.lstrip(".")).lower()
        if fmt not in {suffix.lstrip(".") for suffix in ORIGIN_FIGURE_SUFFIXES}:
            return _error(
                f"Unsupported output format: {fmt}",
                error_type="unsupported",
                target="output_format",
                value=fmt,
            )
        if fmt == "jpeg":
            fmt = "jpg"
        if fmt == "tiff":
            fmt = "tif"

        def _export(op: Any) -> dict[str, Any]:
            graph = self._find_graph(op, graph_name)
            graph.save_fig(str(path), type=fmt, width=width)
            actual_graph_name = getattr(graph, "name", graph_name or self._active_graph or "")
            self._active_graph = actual_graph_name
            return {
                "graph_name": actual_graph_name,
                "output_path": str(path),
                "format": fmt,
                "width": width,
            }

        try:
            data = self._execute(_export)
        except Exception as exc:
            return _error(f"Could not export Origin graph: {exc}")
        return _success("Origin graph exported.", data=data, next_suggestions=["origin_save_project"])

    async def execute_labtalk(self, command: str) -> dict[str, Any]:
        command = command.strip()
        if not command:
            return _error("command cannot be empty.", target="command")
        blocked_reason = self._blocked_labtalk_reason(command)
        if blocked_reason:
            return _error(
                blocked_reason,
                error_type="blocked_unsafe_labtalk",
                target="command",
                value=command,
                hint="Use typed Origin tools for file/project/import/export operations.",
            )

        def _exec(op: Any) -> dict[str, Any]:
            result = op.lt_exec(command)
            return {"command": command, "result": None if result is None else str(result)}

        try:
            data = self._execute(_exec)
        except Exception as exc:
            return _error(f"Could not execute LabTalk command: {exc}")
        return _success(
            "LabTalk command executed.",
            data=data,
            warnings=["LabTalk changes Origin state; verify with origin_get_info or Origin GUI."],
        )

    async def release(self) -> dict[str, Any]:
        was_connected = self._connected
        with self._lock:
            op = self._op
            if op is not None:
                with suppress(Exception):
                    op.detach()
            self._connected = False
            self._op = None
        return _success(
            "Origin COM control released; Origin remains open.",
            data={"was_connected": was_connected},
        )

    def _execute(self, func: Callable[[Any], T]) -> T:
        with self._lock:
            self._ensure_connected()
            if self._op is None:
                raise RuntimeError("Origin is not connected.")
            return func(self._op)

    def _ensure_connected(self) -> None:
        if self._connected and self._op is not None:
            with suppress(Exception):
                self._op.path("e")
                return
            self._connected = False
            self._op = None
        self._connect()

    def _connect(self) -> None:
        try:
            op = importlib.import_module("originpro")
        except ImportError as exc:
            raise RuntimeError(
                "Python package 'originpro' is not installed. Install the optional "
                "Origin dependencies with: pip install 'research-mcp[origin]'."
            ) from exc
        with suppress(Exception):
            if hasattr(op, "attach"):
                op.attach()
        with suppress(Exception):
            op.set_show(self.visible)
        self._op = op
        self._connected = True
        self._refresh_active_context_unlocked(op)

    def _collect_origin_info(self, op: Any) -> dict[str, Any]:
        data: dict[str, Any] = {
            "connected": True,
            "origin_exe": self.origin_exe,
            "active_worksheet": self._active_worksheet,
            "active_graph": self._active_graph,
        }
        with suppress(Exception):
            data["origin_path"] = op.path("e")
        with suppress(Exception):
            data["version"] = str(op.lt_float("@V"))
        graphs = [getattr(graph, "name", str(graph)) for graph in self._iter_pages(op, "Graph")]
        data["graphs"] = graphs
        data["graph_count"] = len(graphs)
        data["workbook_count"] = len(self._iter_pages(op, "Book"))
        self._refresh_active_context_unlocked(op)
        data["active_worksheet"] = self._active_worksheet
        data["active_graph"] = self._active_graph
        return data

    def _refresh_active_context_unlocked(self, op: Any) -> None:
        with suppress(Exception):
            wks = op.find_sheet("w", "")
            if wks:
                self._active_worksheet = self._worksheet_full_name(wks)
        with suppress(Exception):
            graph = op.find_graph("")
            if graph:
                self._active_graph = getattr(graph, "name", None)

    def _find_worksheet(self, op: Any, sheet_name: str = "") -> Any:
        target = sheet_name or self._active_worksheet or ""
        with suppress(Exception):
            wks = op.find_sheet("w", target)
            if wks:
                return wks
        if target:
            raise RuntimeError(f"Worksheet not found: {target}")
        raise RuntimeError("No active Origin worksheet found. Import data or pass sheet_name first.")

    def _find_graph(self, op: Any, graph_name: str = "") -> Any:
        target = graph_name or self._active_graph or ""
        with suppress(Exception):
            graph = op.find_graph(target)
            if graph:
                return graph
        if target:
            raise RuntimeError(f"Graph not found: {target}")
        raise RuntimeError("No active Origin graph found. Create a graph or pass graph_name first.")

    def _worksheet_full_name(self, wks: Any) -> str:
        with suppress(Exception):
            book = wks.get_book()
            return f"[{book.name}]{wks.name}"
        return getattr(wks, "name", str(wks))

    def _worksheet_info(self, wks: Any, preview_rows: int) -> dict[str, Any]:
        info: dict[str, Any] = {
            "name": getattr(wks, "name", str(wks)),
            "full_name": self._worksheet_full_name(wks),
            "rows": getattr(wks, "rows", None),
            "columns": getattr(wks, "cols", None),
        }
        columns: list[dict[str, Any]] = []
        col_count = int(getattr(wks, "cols", 0) or 0)
        for index in range(col_count):
            column_info: dict[str, Any] = {
                "index": index,
                "long_name": self._get_column_label(wks, index, "L"),
                "short_name": self._get_column_label(wks, index, "G"),
                "units": self._get_column_label(wks, index, "U"),
                "designation": self._get_column_label(wks, index, "D"),
            }
            if preview_rows:
                with suppress(Exception):
                    column_info["preview"] = list(wks.to_list(index))[:preview_rows]
            columns.append(column_info)
        info["column_info"] = columns
        return info

    def _get_column_label(self, wks: Any, column_index: int, label_type: str) -> str:
        with suppress(Exception):
            value = wks.get_label(column_index, label_type)
            return "" if value is None else str(value)
        return ""

    def _get_graph_layer(self, graph: Any, index: int) -> Any:
        with suppress(Exception):
            return graph[index]
        with suppress(Exception):
            return graph.layer(index)
        with suppress(Exception):
            return list(graph.layers())[index]
        raise RuntimeError(f"Could not access graph layer {index}.")

    def _iter_pages(self, op: Any, page_type: str) -> list[Any]:
        with suppress(Exception):
            return list(op.pages(page_type))
        return []

    def _iter_book_sheets(self, book: Any) -> list[Any]:
        with suppress(Exception):
            return list(book.layers())
        with suppress(Exception):
            return list(book)
        return []

    def _validate_column_indices(self, indices: list[int], total_cols: int | None) -> None:
        if total_cols is None:
            return
        total = int(total_cols or 0)
        invalid = [index for index in indices if index < 0 or index >= total]
        if invalid:
            raise ValueError(
                f"Column index out of range: {invalid}. Worksheet has {total} columns "
                "and Origin Python indices are 0-based."
            )

    def _resolve_existing_file(
        self, file_path: str, allowed_suffixes: set[str]
    ) -> tuple[Path | None, dict[str, Any] | None]:
        path = Path(file_path).expanduser().resolve()
        if not path.exists() or not path.is_file():
            return None, _error(
                f"File not found: {path}",
                error_type="invalid_input",
                target="file_path",
                value=file_path,
            )
        suffix = path.suffix.lower()
        if suffix not in allowed_suffixes:
            return None, _error(
                f"Unsupported file suffix '{suffix}'.",
                error_type="unsupported",
                target="file_path",
                value=file_path,
                hint=f"Allowed suffixes: {', '.join(sorted(allowed_suffixes))}",
            )
        return path, None

    def _resolve_output_path(
        self, output_path: str, allowed_suffixes: set[str]
    ) -> tuple[Path | None, dict[str, Any] | None]:
        path = Path(output_path).expanduser().resolve()
        suffix = path.suffix.lower()
        if suffix not in allowed_suffixes:
            return None, _error(
                f"Unsupported output suffix '{suffix}'.",
                error_type="unsupported",
                target="output_path",
                value=output_path,
                hint=f"Allowed suffixes: {', '.join(sorted(allowed_suffixes))}",
            )
        path.parent.mkdir(parents=True, exist_ok=True)
        return path, None

    def _blocked_labtalk_reason(self, command: str) -> str:
        for pattern in DANGEROUS_LABTALK_PATTERNS:
            if pattern.search(command):
                return f"Blocked unsafe LabTalk command matching pattern: {pattern.pattern}"
        return ""

    def _detect_origin_exe(self) -> str:
        for installation in self._find_origin_installations():
            display_icon = str(installation.get("display_icon") or "")
            if display_icon and Path(display_icon).exists():
                return display_icon
            install_location = str(installation.get("install_location") or "")
            if install_location:
                for exe_name in ("Origin64.exe", "Origin.exe"):
                    candidate = Path(install_location) / exe_name
                    if candidate.exists():
                        return str(candidate)
        return "Origin64.exe"

    def _find_origin_installations(self) -> list[dict[str, Any]]:
        if platform.system() != "Windows":
            return []
        try:
            import winreg
        except ImportError:
            return []

        registry_paths = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
            (
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
            ),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        ]
        installations: list[dict[str, Any]] = []
        for root, key_path in registry_paths:
            with suppress(OSError):
                key = winreg.OpenKey(root, key_path)
                index = 0
                while True:
                    try:
                        subkey_name = winreg.EnumKey(key, index)
                    except OSError:
                        break
                    index += 1
                    with suppress(OSError):
                        subkey = winreg.OpenKey(key, subkey_name)
                        display_name = self._query_registry_value(winreg, subkey, "DisplayName")
                        publisher = self._query_registry_value(winreg, subkey, "Publisher")
                        if not self._looks_like_originlab(display_name, publisher):
                            continue
                        installations.append(
                            {
                                "display_name": display_name,
                                "display_version": self._query_registry_value(
                                    winreg, subkey, "DisplayVersion"
                                ),
                                "publisher": publisher,
                                "install_location": self._query_registry_value(
                                    winreg, subkey, "InstallLocation"
                                ),
                                "display_icon": self._query_registry_value(
                                    winreg, subkey, "DisplayIcon"
                                ),
                            }
                        )
        return installations

    def _query_registry_value(self, winreg: Any, key: Any, name: str) -> str:
        try:
            value, _value_type = winreg.QueryValueEx(key, name)
        except OSError:
            return ""
        return str(value)

    def _looks_like_originlab(self, display_name: str, publisher: str) -> bool:
        name = display_name.strip().lower()
        pub = publisher.strip().lower()
        return "originlab" in pub or "originlab" in name or name.startswith("origin ") or name.startswith(
            "originpro"
        )
