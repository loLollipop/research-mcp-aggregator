"""Local MATLAB command-line adapter using MATLAB's ``-batch`` mode."""

from __future__ import annotations

import csv
import os
from pathlib import Path
from typing import Any

from research_mcp.adapters import AdapterMeta, BaseAdapter, ToolSpec, register_adapter
from research_mcp.simulation.command_utils import (
    require_file,
    resolve_working_dir,
    run_command,
    validate_executable_command,
)

MATLAB_FILE_SUFFIXES = {".m", ".mlx"}
MATLAB_TABLE_SUFFIXES = {".csv", ".tsv", ".txt"}
MATLAB_FIGURE_SUFFIXES = {".eps", ".jpg", ".jpeg", ".pdf", ".png", ".svg", ".tif", ".tiff"}
MATLAB_NOTICE = {
    "role": "assistant_control_surface_for_existing_local_matlab",
    "summary": (
        "Runs installed MATLAB through command-line batch mode; it does not replace "
        "MATLAB licensing, toolbox availability, numerical validation, or expert review."
    ),
    "requires_user_review": True,
}


@register_adapter
class MatlabAdapter(BaseAdapter):
    """Expose local MATLAB command-line workflows to MCP clients."""

    adapter_name = "matlab"

    def __init__(self) -> None:
        self.matlab_cmd = "matlab"
        self.timeout_seconds = 600

    def metadata(self) -> AdapterMeta:
        return AdapterMeta(
            name="matlab",
            description="Local MATLAB command-line tools using MATLAB -batch workflows",
            tools=[
                ToolSpec(
                    name="matlab_check_config",
                    description="Show configured MATLAB command and execution boundary.",
                    input_schema={"type": "object", "properties": {}},
                    handler=self.check_config,
                ),
                ToolSpec(
                    name="matlab_create_script",
                    description="Create a local MATLAB .m script or function file.",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "file_path": {
                                "type": "string",
                                "description": "Output .m file path",
                                "minLength": 1,
                            },
                            "code": {
                                "type": "string",
                                "description": "MATLAB source code to write",
                                "minLength": 1,
                            },
                            "overwrite": {"type": "boolean", "default": False},
                        },
                        "required": ["file_path", "code"],
                    },
                    handler=self.create_script,
                ),
                ToolSpec(
                    name="matlab_check_code",
                    description="Dry-run or run MATLAB checkcode on code or a local .m file.",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "code": {
                                "type": "string",
                                "description": "Optional MATLAB code to check",
                            },
                            "file_path": {
                                "type": "string",
                                "description": "Optional existing .m file to check",
                            },
                            "working_dir": {
                                "type": "string",
                                "description": "Optional working directory",
                            },
                            "dry_run": {"type": "boolean", "default": True},
                            "timeout_seconds": {
                                "type": "integer",
                                "description": "Timeout seconds",
                                "minimum": 1,
                                "maximum": 3600,
                            },
                        },
                    },
                    handler=self.check_code,
                ),
                ToolSpec(
                    name="matlab_evaluate_code",
                    description="Dry-run or execute MATLAB code through MATLAB -batch.",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "code": {
                                "type": "string",
                                "description": "MATLAB code to execute",
                                "minLength": 1,
                            },
                            "working_dir": {
                                "type": "string",
                                "description": "Optional working directory",
                            },
                            "dry_run": {"type": "boolean", "default": True},
                            "timeout_seconds": {
                                "type": "integer",
                                "description": "Timeout seconds",
                                "minimum": 1,
                                "maximum": 7200,
                            },
                        },
                        "required": ["code"],
                    },
                    handler=self.evaluate_code,
                ),
                ToolSpec(
                    name="matlab_run_file",
                    description="Dry-run or run a local MATLAB .m/.mlx file through MATLAB -batch.",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "file_path": {
                                "type": "string",
                                "description": "Path to .m or .mlx file",
                                "minLength": 1,
                            },
                            "working_dir": {
                                "type": "string",
                                "description": "Optional working directory",
                            },
                            "dry_run": {"type": "boolean", "default": True},
                            "timeout_seconds": {
                                "type": "integer",
                                "description": "Timeout seconds",
                                "minimum": 1,
                                "maximum": 7200,
                            },
                        },
                        "required": ["file_path"],
                    },
                    handler=self.run_file,
                ),
                ToolSpec(
                    name="matlab_run_test_file",
                    description="Dry-run or run a MATLAB test file using runtests in -batch mode.",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "file_path": {
                                "type": "string",
                                "description": "Path to MATLAB test .m file",
                                "minLength": 1,
                            },
                            "working_dir": {
                                "type": "string",
                                "description": "Optional working directory",
                            },
                            "dry_run": {"type": "boolean", "default": True},
                            "timeout_seconds": {
                                "type": "integer",
                                "description": "Timeout seconds",
                                "minimum": 1,
                                "maximum": 7200,
                            },
                        },
                        "required": ["file_path"],
                    },
                    handler=self.run_test_file,
                ),
                ToolSpec(
                    name="matlab_detect_toolboxes",
                    description="Dry-run or list installed MATLAB toolboxes using ver.",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "working_dir": {
                                "type": "string",
                                "description": "Optional working directory",
                            },
                            "dry_run": {"type": "boolean", "default": True},
                            "timeout_seconds": {
                                "type": "integer",
                                "description": "Timeout seconds",
                                "minimum": 1,
                                "maximum": 3600,
                            },
                        },
                    },
                    handler=self.detect_toolboxes,
                ),
                ToolSpec(
                    name="matlab_parse_table",
                    description="Parse a MATLAB-exported CSV/TSV table and summarize columns.",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "table_path": {
                                "type": "string",
                                "description": "Path to CSV/TSV/TXT table exported by MATLAB",
                                "minLength": 1,
                            },
                            "delimiter": {
                                "type": "string",
                                "enum": ["auto", "comma", "tab", "semicolon"],
                                "default": "auto",
                            },
                            "preview_rows": {
                                "type": "integer",
                                "description": "Number of preview rows to return",
                                "default": 5,
                                "minimum": 0,
                                "maximum": 50,
                            },
                        },
                        "required": ["table_path"],
                    },
                    handler=self.parse_table,
                ),
                ToolSpec(
                    name="matlab_create_plot_export_script",
                    description=(
                        "Create a MATLAB script that plots table columns and exports a figure."
                    ),
                    input_schema={
                        "type": "object",
                        "properties": {
                            "table_path": {
                                "type": "string",
                                "description": "Input CSV/TSV/TXT table path",
                                "minLength": 1,
                            },
                            "x_column": {
                                "type": "string",
                                "description": "Table column to use as x data",
                                "minLength": 1,
                            },
                            "y_column": {
                                "type": "string",
                                "description": "Table column to use as y data",
                                "minLength": 1,
                            },
                            "output_script": {
                                "type": "string",
                                "description": "Output MATLAB .m script path",
                                "minLength": 1,
                            },
                            "output_figure": {
                                "type": "string",
                                "description": "Output figure path (.png/.svg/.pdf/etc.)",
                                "minLength": 1,
                            },
                            "title": {"type": "string", "description": "Optional plot title"},
                            "xlabel": {"type": "string", "description": "Optional x axis label"},
                            "ylabel": {"type": "string", "description": "Optional y axis label"},
                            "kind": {
                                "type": "string",
                                "enum": ["line", "scatter"],
                                "default": "line",
                            },
                            "overwrite": {"type": "boolean", "default": False},
                        },
                        "required": [
                            "table_path",
                            "x_column",
                            "y_column",
                            "output_script",
                            "output_figure",
                        ],
                    },
                    handler=self.create_plot_export_script,
                ),
            ],
        )

    async def initialize(self, config: dict[str, Any] | None = None) -> None:
        cfg = config or {}
        self.matlab_cmd = validate_executable_command(
            cfg.get("matlab_cmd") or os.environ.get("MATLAB_CMD", "matlab")
        )
        self.timeout_seconds = int(
            cfg.get("timeout_seconds") or os.environ.get("MATLAB_TIMEOUT_SECONDS", "600")
        )

    async def check_config(self) -> dict[str, Any]:
        return {
            "matlab_cmd": self.matlab_cmd,
            "timeout_seconds": self.timeout_seconds,
            "scope_notice": MATLAB_NOTICE,
            "env": {
                "MATLAB_CMD": os.environ.get("MATLAB_CMD", ""),
                "MATLAB_TIMEOUT_SECONDS": os.environ.get("MATLAB_TIMEOUT_SECONDS", ""),
            },
        }

    async def create_script(
        self,
        file_path: str,
        code: str,
        overwrite: bool = False,
    ) -> dict[str, Any]:
        path = Path(file_path).expanduser().resolve()
        if path.suffix.lower() != ".m":
            raise ValueError("MATLAB script/function files must use the .m suffix")
        if path.exists() and not overwrite:
            raise FileExistsError(f"MATLAB file already exists: {path}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(code, encoding="utf-8")
        return {"status": "ok", "file_path": str(path), "bytes": path.stat().st_size}

    async def check_code(
        self,
        code: str = "",
        file_path: str = "",
        working_dir: str = "",
        dry_run: bool = True,
        timeout_seconds: int = 0,
    ) -> dict[str, Any]:
        cwd = self._working_dir(working_dir)
        if file_path:
            target = self._require_matlab_file(file_path, allowed_suffixes={".m"})
            command = f"checkcode('{self._matlab_string(str(target))}')"
            input_files = {"file_path": str(target)}
        elif code.strip():
            command = self._check_inline_code_command(code)
            input_files = {"code": "inline"}
        else:
            raise ValueError("Provide either code or file_path")
        return await self._run_batch(
            command=command,
            cwd=cwd,
            dry_run=dry_run,
            timeout_seconds=timeout_seconds,
            tool="matlab_check_code",
            input_files=input_files,
        )

    async def evaluate_code(
        self,
        code: str,
        working_dir: str = "",
        dry_run: bool = True,
        timeout_seconds: int = 0,
    ) -> dict[str, Any]:
        return await self._run_batch(
            command=code,
            cwd=self._working_dir(working_dir),
            dry_run=dry_run,
            timeout_seconds=timeout_seconds,
            tool="matlab_evaluate_code",
            input_files={"code": "inline"},
        )

    async def run_file(
        self,
        file_path: str,
        working_dir: str = "",
        dry_run: bool = True,
        timeout_seconds: int = 0,
    ) -> dict[str, Any]:
        path = self._require_matlab_file(file_path)
        command = f"run('{self._matlab_string(str(path))}')"
        return await self._run_batch(
            command=command,
            cwd=self._working_dir(working_dir or str(path.parent)),
            dry_run=dry_run,
            timeout_seconds=timeout_seconds,
            tool="matlab_run_file",
            input_files={"file_path": str(path)},
        )

    async def run_test_file(
        self,
        file_path: str,
        working_dir: str = "",
        dry_run: bool = True,
        timeout_seconds: int = 0,
    ) -> dict[str, Any]:
        path = self._require_matlab_file(file_path, allowed_suffixes={".m"})
        command = (
            f"results = runtests('{self._matlab_string(str(path))}'); "
            "disp(table(results)); assertSuccess(results);"
        )
        return await self._run_batch(
            command=command,
            cwd=self._working_dir(working_dir or str(path.parent)),
            dry_run=dry_run,
            timeout_seconds=timeout_seconds,
            tool="matlab_run_test_file",
            input_files={"file_path": str(path)},
        )

    async def detect_toolboxes(
        self,
        working_dir: str = "",
        dry_run: bool = True,
        timeout_seconds: int = 0,
    ) -> dict[str, Any]:
        command = (
            "v = ver; "
            "Name = {v.Name}'; Version = {v.Version}'; Release = {v.Release}'; "
            "disp(table(Name, Version, Release))"
        )
        return await self._run_batch(
            command=command,
            cwd=self._working_dir(working_dir),
            dry_run=dry_run,
            timeout_seconds=timeout_seconds,
            tool="matlab_detect_toolboxes",
            input_files={},
        )

    async def parse_table(
        self,
        table_path: str,
        delimiter: str = "auto",
        preview_rows: int = 5,
    ) -> dict[str, Any]:
        if delimiter not in {"auto", "comma", "tab", "semicolon"}:
            raise ValueError("delimiter must be one of: auto, comma, tab, semicolon")
        path = self._require_table_file(table_path)
        dialect_delimiter = self._resolve_delimiter(path, delimiter)
        preview_limit = max(0, min(int(preview_rows), 50))
        rows: list[dict[str, str]] = []
        with path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle, delimiter=dialect_delimiter)
            columns = list(reader.fieldnames or [])
            for row in reader:
                rows.append({key: value for key, value in row.items() if key is not None})
        return {
            "status": "ok",
            "table_path": str(path),
            "delimiter": dialect_delimiter,
            "row_count": len(rows),
            "columns": columns,
            "preview_rows": rows[:preview_limit],
            "numeric_summary": self._numeric_summary(rows, columns),
        }

    async def create_plot_export_script(
        self,
        table_path: str,
        x_column: str,
        y_column: str,
        output_script: str,
        output_figure: str,
        title: str = "",
        xlabel: str = "",
        ylabel: str = "",
        kind: str = "line",
        overwrite: bool = False,
    ) -> dict[str, Any]:
        if kind not in {"line", "scatter"}:
            raise ValueError("kind must be 'line' or 'scatter'")
        table = self._require_table_file(table_path)
        script = Path(output_script).expanduser().resolve()
        figure = Path(output_figure).expanduser().resolve()
        if script.suffix.lower() != ".m":
            raise ValueError("MATLAB plot export script must use the .m suffix")
        if figure.suffix.lower() not in MATLAB_FIGURE_SUFFIXES:
            allowed = ", ".join(sorted(MATLAB_FIGURE_SUFFIXES))
            raise ValueError(f"Unsupported figure output suffix. Allowed suffixes: {allowed}")
        self._require_table_columns(table, {x_column, y_column})
        if script.exists() and not overwrite:
            raise FileExistsError(f"MATLAB script already exists: {script}")
        script.parent.mkdir(parents=True, exist_ok=True)
        figure.parent.mkdir(parents=True, exist_ok=True)
        script.write_text(
            self._plot_export_script(
                table=table,
                x_column=x_column,
                y_column=y_column,
                output_figure=figure,
                title=title,
                xlabel=xlabel or x_column,
                ylabel=ylabel or y_column,
                kind=kind,
            ),
            encoding="utf-8",
        )
        return {
            "status": "ok",
            "script_path": str(script),
            "table_path": str(table),
            "output_figure": str(figure),
            "kind": kind,
            "bytes": script.stat().st_size,
            "next_action": "Review the generated script, then run it with matlab_run_file.",
        }

    def _working_dir(self, working_dir: str) -> Path:
        return resolve_working_dir(working_dir, Path.cwd())

    def _require_table_file(self, table_path: str) -> Path:
        path = require_file(table_path)
        if path.suffix.lower() not in MATLAB_TABLE_SUFFIXES:
            allowed = ", ".join(sorted(MATLAB_TABLE_SUFFIXES))
            raise ValueError(f"Expected MATLAB table export suffix in {{{allowed}}}: {path}")
        return path

    def _require_matlab_file(
        self,
        file_path: str,
        allowed_suffixes: set[str] | None = None,
    ) -> Path:
        path = require_file(file_path)
        allowed = allowed_suffixes or MATLAB_FILE_SUFFIXES
        if path.suffix.lower() not in allowed:
            allowed_text = ", ".join(sorted(allowed))
            raise ValueError(f"Expected MATLAB file suffix in {{{allowed_text}}}: {path}")
        return path

    async def _run_batch(
        self,
        *,
        command: str,
        cwd: Path,
        dry_run: bool,
        timeout_seconds: int,
        tool: str,
        input_files: dict[str, str],
    ) -> dict[str, Any]:
        args = [self.matlab_cmd, "-batch", command]
        timeout = timeout_seconds or self.timeout_seconds
        if dry_run:
            return {
                "status": "dry_run",
                "tool": tool,
                "command": args,
                "cwd": str(cwd),
                "timeout_seconds": timeout,
                "input_files": input_files,
                "scope_notice": MATLAB_NOTICE,
                "next_action": "Review the command, then rerun with dry_run=false to execute.",
            }
        result = await run_command(args, cwd, timeout)
        result["tool"] = tool
        result["scope_notice"] = MATLAB_NOTICE
        return result

    def _matlab_string(self, value: str) -> str:
        return value.replace("'", "''")

    def _matlab_string_literal(self, value: str) -> str:
        return "'" + self._matlab_string(value) + "'"

    def _check_inline_code_command(self, code: str) -> str:
        code_literal = self._matlab_string_literal(code)
        return (
            "tmp = [tempname '.m']; "
            "cleanup = onCleanup(@() delete(tmp)); "
            "fid = fopen(tmp, 'w'); "
            "if fid < 0, error('Could not create temporary checkcode file'); end; "
            f"fwrite(fid, {code_literal}, 'char'); "
            "fclose(fid); "
            "checkcode(tmp)"
        )

    def _resolve_delimiter(self, path: Path, delimiter: str) -> str:
        if delimiter == "comma":
            return ","
        if delimiter == "tab":
            return "\t"
        if delimiter == "semicolon":
            return ";"
        if path.suffix.lower() == ".tsv":
            return "\t"
        sample = path.read_text(encoding="utf-8-sig")[:2048]
        try:
            return csv.Sniffer().sniff(sample, delimiters=",\t;").delimiter
        except csv.Error:
            return ","

    def _require_table_columns(self, path: Path, required_columns: set[str]) -> None:
        delimiter = self._resolve_delimiter(path, "auto")
        with path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.reader(handle, delimiter=delimiter)
            columns = next(reader, [])
        missing = sorted(column for column in required_columns if column not in columns)
        if missing:
            available = ", ".join(columns) if columns else "<none>"
            raise ValueError(
                "Table column not found: "
                f"{', '.join(missing)}. Available columns: {available}"
            )

    def _numeric_summary(
        self,
        rows: list[dict[str, str]],
        columns: list[str],
    ) -> dict[str, dict[str, float | int]]:
        summary: dict[str, dict[str, float | int]] = {}
        for column in columns:
            values: list[float] = []
            for row in rows:
                raw = (row.get(column) or "").strip()
                if not raw:
                    continue
                try:
                    values.append(float(raw))
                except ValueError:
                    continue
            if values:
                summary[column] = {
                    "count": len(values),
                    "min": min(values),
                    "max": max(values),
                    "mean": sum(values) / len(values),
                }
        return summary

    def _plot_export_script(
        self,
        *,
        table: Path,
        x_column: str,
        y_column: str,
        output_figure: Path,
        title: str,
        xlabel: str,
        ylabel: str,
        kind: str,
    ) -> str:
        plot_command = (
            "scatter(x, y, 24, 'filled');"
            if kind == "scatter"
            else "plot(x, y, 'LineWidth', 1.8);"
        )
        x_name = self._matlab_string_literal(x_column)
        y_name = self._matlab_string_literal(y_column)
        figure_path = self._matlab_string_literal(str(output_figure))
        return "\n".join(
            [
                "% Generated by research-mcp matlab_create_plot_export_script",
                f"tbl = readtable({self._matlab_string_literal(str(table))});",
                f"x = tbl{{:, matlab.lang.makeValidName({x_name})}};",
                f"y = tbl{{:, matlab.lang.makeValidName({y_name})}};",
                "fig = figure('Visible', 'off');",
                plot_command,
                "grid on;",
                f"title({self._matlab_string_literal(title)});" if title else "",
                f"xlabel({self._matlab_string_literal(xlabel)});" if xlabel else "",
                f"ylabel({self._matlab_string_literal(ylabel)});" if ylabel else "",
                f"exportgraphics(fig, {figure_path}, 'Resolution', 300);",
                "close(fig);",
                "",
            ]
        )
