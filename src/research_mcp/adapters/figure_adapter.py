"""Figure adapter for research plotting.

Provides lightweight publication-oriented plotting tools that save SVG/PNG
outputs locally for papers, reports, and presentations.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from research_mcp.adapters import AdapterMeta, BaseAdapter, ToolSpec, register_adapter


@register_adapter
class FigureAdapter(BaseAdapter):
    """Generate simple publication-ready figures from arrays or CSV files."""

    adapter_name = "figure"

    def metadata(self) -> AdapterMeta:
        return AdapterMeta(
            name="figure",
            description="Scientific figure generation: XY plots and CSV plotting to SVG/PNG",
            tools=[
                ToolSpec(
                    name="plot_xy",
                    description="Create an XY line/scatter plot and save SVG/PNG/PDF output.",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "x": {"type": "array", "items": {"type": "number"}, "minItems": 1},
                            "y": {"type": "array", "items": {"type": "number"}, "minItems": 1},
                            "output_path": {
                                "type": "string",
                                "description": "Output file path (.svg/.png/.pdf)",
                                "minLength": 1,
                            },
                            "title": {"type": "string"},
                            "xlabel": {"type": "string"},
                            "ylabel": {"type": "string"},
                            "kind": {
                                "type": "string",
                                "enum": ["line", "scatter"],
                                "default": "line",
                            },
                        },
                        "required": ["x", "y", "output_path"],
                    },
                    handler=self.plot_xy,
                ),
                ToolSpec(
                    name="plot_csv_columns",
                    description="Create a plot from two numeric columns in a CSV file.",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "csv_path": {
                                "type": "string",
                                "description": "Input CSV file",
                                "minLength": 1,
                            },
                            "x_column": {
                                "type": "string",
                                "description": "Column name for x",
                                "minLength": 1,
                            },
                            "y_column": {
                                "type": "string",
                                "description": "Column name for y",
                                "minLength": 1,
                            },
                            "output_path": {
                                "type": "string",
                                "description": "Output file path",
                                "minLength": 1,
                            },
                            "title": {"type": "string"},
                            "xlabel": {"type": "string"},
                            "ylabel": {"type": "string"},
                            "kind": {
                                "type": "string",
                                "enum": ["line", "scatter"],
                                "default": "line",
                            },
                        },
                        "required": ["csv_path", "x_column", "y_column", "output_path"],
                    },
                    handler=self.plot_csv_columns,
                ),
            ],
        )

    async def initialize(self, config: dict[str, Any] | None = None) -> None:
        pass

    async def plot_xy(
        self,
        x: list[float],
        y: list[float],
        output_path: str,
        title: str = "",
        xlabel: str = "",
        ylabel: str = "",
        kind: str = "line",
    ) -> dict[str, Any]:
        if len(x) != len(y):
            raise ValueError("x and y must have the same length")
        output = Path(output_path).expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        self._plot(x, y, output, title, xlabel, ylabel, kind)
        return {"output_path": str(output), "points": len(x), "kind": kind}

    async def plot_csv_columns(
        self,
        csv_path: str,
        x_column: str,
        y_column: str,
        output_path: str,
        title: str = "",
        xlabel: str = "",
        ylabel: str = "",
        kind: str = "line",
    ) -> dict[str, Any]:
        path = Path(csv_path).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"CSV not found: {path}")
        x: list[float] = []
        y: list[float] = []
        with path.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                x.append(float(row[x_column]))
                y.append(float(row[y_column]))
        return await self.plot_xy(
            x, y, output_path, title, xlabel or x_column, ylabel or y_column, kind
        )

    def _plot(
        self,
        x: list[float],
        y: list[float],
        output: Path,
        title: str,
        xlabel: str,
        ylabel: str,
        kind: str,
    ) -> None:
        import matplotlib.pyplot as plt

        plt.rcParams.update({"font.size": 11, "axes.linewidth": 1.0})
        fig, ax = plt.subplots(figsize=(5.2, 3.6), constrained_layout=True)
        if kind == "scatter":
            ax.scatter(x, y, s=24)
        else:
            ax.plot(x, y, linewidth=1.8)
        if title:
            ax.set_title(title)
        if xlabel:
            ax.set_xlabel(xlabel)
        if ylabel:
            ax.set_ylabel(ylabel)
        ax.grid(True, alpha=0.25)
        fig.savefig(output, dpi=300)
        plt.close(fig)
