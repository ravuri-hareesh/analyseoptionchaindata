from __future__ import annotations

from pathlib import Path
from typing import Optional

import matplotlib.pyplot as plt

from analysis import Level


def plot_support_resistance(
    analysis_result,
    output_path: Optional[str] = None,
    show: bool = False,
    title: str = "NSE Option Chain: Support/Resistance (OI Peaks)",
):
    data = analysis_result["data"]
    max_support: Level = analysis_result["max_support"]
    max_resistance: Level = analysis_result["max_resistance"]
    top_support = analysis_result["top_support"]
    top_resistance = analysis_result["top_resistance"]
    smooth_window = analysis_result.get("smooth_window", 1)

    fig, ax = plt.subplots(figsize=(12, 6))

    ax.plot(data["strike"], data["pe_oi_s"], label="Put OI (Support)", color="green", linewidth=2)
    ax.plot(data["strike"], data["ce_oi_s"], label="Call OI (Resistance)", color="red", linewidth=2)

    # Mark top N points
    ax.scatter(
        [lv.strike for lv in top_support],
        [lv.pe_oi for lv in top_support],
        color="green",
        marker="o",
        s=55,
        label=f"Top Support ({len(top_support)})",
        zorder=5,
    )
    ax.scatter(
        [lv.strike for lv in top_resistance],
        [lv.ce_oi for lv in top_resistance],
        color="red",
        marker="o",
        s=55,
        label=f"Top Resistance ({len(top_resistance)})",
        zorder=5,
    )

    # Highlight maxima with vertical lines
    ax.axvline(max_support.strike, color="green", linestyle="--", linewidth=2, alpha=0.9)
    ax.axvline(max_resistance.strike, color="red", linestyle="--", linewidth=2, alpha=0.9)

    # Labels
    ax.annotate(
        f"Max Support\n{max_support.strike:.0f}",
        xy=(max_support.strike, max_support.pe_oi),
        xytext=(5, 10),
        textcoords="offset points",
        color="green",
        fontsize=11,
        arrowprops=dict(arrowstyle="->", color="green"),
    )
    ax.annotate(
        f"Max Resistance\n{max_resistance.strike:.0f}",
        xy=(max_resistance.strike, max_resistance.ce_oi),
        xytext=(5, -25),
        textcoords="offset points",
        color="red",
        fontsize=11,
        arrowprops=dict(arrowstyle="->", color="red"),
    )

    ax.set_xlabel("Strike Price")
    ax.set_ylabel("Open Interest (OI)")
    ax.grid(True, alpha=0.25)

    subtitle = f"(Smoothed OI: window={smooth_window})" if smooth_window and smooth_window > 1 else "(Raw OI)"
    ax.set_title(f"{title}\n{subtitle}")

    ax.legend(loc="best")
    fig.tight_layout()

    if output_path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(out, dpi=160)

    if show:
        plt.show()
    else:
        plt.close(fig)

