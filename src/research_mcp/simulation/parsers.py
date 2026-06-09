"""Table parsers for simulation outputs."""

from __future__ import annotations

import csv
import re
from pathlib import Path

_NUMERIC_PREFIX = re.compile(
    r"^[\s\"']*([+-]?(?:(?:\d+(?:\.\d*)?)|(?:\.\d+))(?:[eEdD][+-]?\d+)?|[+-]?(?:inf|nan))",
    re.IGNORECASE,
)


def parse_numeric_table(path: Path) -> dict[str, list[float]]:
    lines = _read_data_lines(path, strip_comsol_comment=True)
    if not lines:
        raise ValueError(f"Table file is empty: {path}")
    rows = _split_rows(lines)
    first = rows[0]
    if is_numeric_row(first):
        header = [f"column_{index + 1}" for index in range(len(first))]
        numeric_rows = rows
    else:
        header = _unique_names(
            [normalize_residual_name(name, index) for index, name in enumerate(first)]
        )
        numeric_rows = rows[1:]
    return _numeric_columns(header, numeric_rows, f"No numeric rows parsed from table: {path}")


def parse_residual_table(path: Path) -> dict[str, list[float]]:
    data, _source_independent = parse_history_table(path)
    return data


def parse_history_table(path: Path) -> tuple[dict[str, list[float]], str]:
    lines = _read_data_lines(path, strip_comsol_comment=False)
    if not lines:
        raise ValueError(f"Residual file is empty: {path}")
    rows = _split_rows(lines)
    header, numeric_rows, source_independent = split_residual_header_with_source(rows)
    columns = _numeric_columns(
        header,
        numeric_rows,
        f"No numeric rows parsed from residual/history file: {path}",
    )
    if not columns.get("iteration"):
        row_count = max((len(values) for values in columns.values()), default=0)
        columns["iteration"] = [float(index + 1) for index in range(row_count)]
    return columns, source_independent


def split_residual_header(rows: list[list[str]]) -> tuple[list[str], list[list[str]]]:
    header, numeric_rows, _source_independent = split_residual_header_with_source(rows)
    return header, numeric_rows


def split_residual_header_with_source(
    rows: list[list[str]],
) -> tuple[list[str], list[list[str]], str]:
    first = rows[0]
    if is_numeric_row(first):
        names = ["iteration", *[f"residual_{index}" for index in range(1, len(first))]]
        return names, rows, "iteration"
    names = [normalize_residual_name(name, index) for index, name in enumerate(first)]
    source_independent = names[0] if names else "iteration"
    if names and names[0] not in {"iteration", "iter", "time_step"}:
        names[0] = "iteration"
    else:
        names[0] = "iteration"
    return _unique_names(names), rows[1:], source_independent


def is_numeric_row(row: list[str]) -> bool:
    return bool(row) and all(_coerce_float(value) is not None for value in row)


def normalize_residual_name(name: str, index: int) -> str:
    normalized = name.strip().lower().replace(" ", "_").replace("-", "_")
    return normalized or f"residual_{index}"


def _read_data_lines(path: Path, strip_comsol_comment: bool) -> list[str]:
    lines: list[str] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if strip_comsol_comment:
            line = line.lstrip("%").strip()
        if not line or line.startswith(("#", ";")):
            continue
        line = _strip_inline_comment(line)
        if line:
            lines.append(line)
    return lines


def _strip_inline_comment(line: str) -> str:
    for marker in (" #", "\t#", " ;", "\t;"):
        index = line.find(marker)
        if index >= 0:
            line = line[:index]
    return line.strip()


def _split_rows(lines: list[str]) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in lines:
        if "," in line:
            parsed = next(csv.reader([line], skipinitialspace=True))
        else:
            parsed = line.split()
        row = [cell.strip() for cell in parsed if cell.strip()]
        if row:
            rows.append(row)
    return rows


def _numeric_columns(
    header: list[str],
    numeric_rows: list[list[str]],
    empty_error: str,
) -> dict[str, list[float]]:
    columns: dict[str, list[float]] = {name: [] for name in header}
    valid_rows = 0
    for row in numeric_rows:
        if len(row) < len(header):
            continue
        values = [_coerce_float(value) for value in row[: len(header)]]
        if any(value is None for value in values):
            continue
        for name, value in zip(header, values):
            assert value is not None
            columns[name].append(value)
        valid_rows += 1
    if valid_rows == 0:
        raise ValueError(empty_error)
    return columns


def _coerce_float(value: str) -> float | None:
    stripped = value.strip().strip('"').strip("'")
    if not stripped:
        return None
    try:
        return float(stripped.replace("D", "E").replace("d", "e"))
    except ValueError:
        match = _NUMERIC_PREFIX.match(stripped)
        if not match:
            return None
        try:
            return float(match.group(1).replace("D", "E").replace("d", "e"))
        except ValueError:
            return None


def _unique_names(names: list[str]) -> list[str]:
    counts: dict[str, int] = {}
    unique: list[str] = []
    for name in names:
        count = counts.get(name, 0)
        counts[name] = count + 1
        unique.append(name if count == 0 else f"{name}_{count + 1}")
    return unique


def summarize_series(values: list[float]) -> dict[str, float]:
    if not values:
        return {"min": 0.0, "max": 0.0, "mean": 0.0, "final": 0.0}
    return {
        "min": min(values),
        "max": max(values),
        "mean": sum(values) / len(values),
        "final": values[-1],
    }
