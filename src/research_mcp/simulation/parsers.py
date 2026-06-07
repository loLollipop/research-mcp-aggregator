"""Table parsers for simulation outputs."""

from __future__ import annotations

import csv
from pathlib import Path


def parse_numeric_table(path: Path) -> dict[str, list[float]]:
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines()]
    lines = [line.lstrip("%").strip() for line in lines if line and not line.startswith(("#", ";"))]
    lines = [line for line in lines if line]
    if not lines:
        raise ValueError(f"Table file is empty: {path}")
    delimiter = "," if "," in lines[0] else None
    rows = list(csv.reader(lines, delimiter=delimiter or " ", skipinitialspace=True))
    rows = [[cell for cell in row if cell] for row in rows]
    first = rows[0]
    if is_numeric_row(first):
        header = [f"column_{index + 1}" for index in range(len(first))]
        numeric_rows = rows
    else:
        header = [normalize_residual_name(name, index) for index, name in enumerate(first)]
        numeric_rows = rows[1:]
    columns = {name: [] for name in header}
    for row in numeric_rows:
        if len(row) < len(header):
            continue
        for name, value in zip(header, row):
            columns[name].append(float(value))
    return columns


def parse_residual_table(path: Path) -> dict[str, list[float]]:
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines()]
    lines = [line for line in lines if line and not line.startswith(("#", ";"))]
    if not lines:
        raise ValueError(f"Residual file is empty: {path}")
    delimiter = "," if "," in lines[0] else None
    rows = list(csv.reader(lines, delimiter=delimiter or " ", skipinitialspace=True))
    rows = [[cell for cell in row if cell] for row in rows]
    header, numeric_rows = split_residual_header(rows)
    columns = {name: [] for name in header}
    for row in numeric_rows:
        if len(row) < len(header):
            continue
        for name, value in zip(header, row):
            columns[name].append(float(value))
    if not columns.get("iteration"):
        columns["iteration"] = [float(index + 1) for index in range(len(numeric_rows))]
    return columns


def split_residual_header(rows: list[list[str]]) -> tuple[list[str], list[list[str]]]:
    first = rows[0]
    if is_numeric_row(first):
        names = ["iteration", *[f"residual_{index}" for index in range(1, len(first))]]
        return names, rows
    names = [normalize_residual_name(name, index) for index, name in enumerate(first)]
    if names and names[0] not in {"iteration", "iter", "time_step"}:
        names[0] = "iteration"
    else:
        names[0] = "iteration"
    return names, rows[1:]


def is_numeric_row(row: list[str]) -> bool:
    try:
        [float(value) for value in row]
        return True
    except ValueError:
        return False


def normalize_residual_name(name: str, index: int) -> str:
    normalized = name.strip().lower().replace(" ", "_").replace("-", "_")
    return normalized or f"residual_{index}"


def summarize_series(values: list[float]) -> dict[str, float]:
    if not values:
        return {"min": 0.0, "max": 0.0, "mean": 0.0, "final": 0.0}
    return {
        "min": min(values),
        "max": max(values),
        "mean": sum(values) / len(values),
        "final": values[-1],
    }
