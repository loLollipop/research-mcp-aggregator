"""Plotting helpers for parsed simulation outputs."""

from __future__ import annotations

from research_mcp.simulation.command_utils import resolve_output_path

PLOT_SUFFIXES = {".svg", ".png", ".pdf"}


def plot_residuals(data: dict[str, list[float]], output_plot: str) -> str:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    output = resolve_output_path(output_plot, allowed_suffixes=PLOT_SUFFIXES)
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


def plot_history(
    data: dict[str, list[float]],
    independent: str,
    output_plot: str,
) -> str:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    output = resolve_output_path(output_plot, allowed_suffixes=PLOT_SUFFIXES)
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
