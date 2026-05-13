from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", str(Path("outputs/.matplotlib").resolve()))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


def plot_equity_curve(
    equity: pd.Series,
    output_path: str | Path,
    metrics: dict[str, float] | None = None,
    title: str = "Equity Curve",
) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(11, 5.6))
    equity.plot(ax=ax, color="#1f77b4", linewidth=1.8)
    ax.set_title(title, loc="left", fontsize=13, fontweight="bold")
    ax.set_xlabel("Date")
    ax.set_ylabel("Portfolio Value")
    ax.grid(True, alpha=0.25)
    if metrics:
        _add_metrics_box(ax, metrics)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)
    return path


def _add_metrics_box(ax, metrics: dict[str, float]) -> None:
    lines = []
    mapping = [
        ("annualized_return", "Annualized Return", "pct"),
        ("annualized_volatility", "Annualized Vol", "pct"),
        ("sharpe", "Sharpe", "num"),
        ("max_drawdown", "Max Drawdown", "pct"),
        ("total_return", "Total Return", "pct"),
        ("annualized_turnover", "Annualized Turnover", "num"),
    ]
    for key, label, kind in mapping:
        if key not in metrics:
            continue
        value = metrics[key]
        if kind == "pct":
            rendered = f"{value:.2%}"
        else:
            rendered = f"{value:.2f}"
        lines.append(f"{label}: {rendered}")
    if not lines:
        return
    ax.text(
        0.985,
        0.965,
        "\n".join(lines),
        transform=ax.transAxes,
        ha="right",
        va="top",
        fontsize=9.5,
        bbox={
            "boxstyle": "round,pad=0.45",
            "facecolor": "white",
            "edgecolor": "#b8c2cc",
            "alpha": 0.92,
        },
    )
