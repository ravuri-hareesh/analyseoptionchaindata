from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt

from nse_option_chain_graph.analysis import compute_support_resistance
from nse_option_chain_graph.io import load_option_chain
from nse_option_chain_graph.analysis import Level


def _label_from_path(p: str) -> str:
    return Path(p).name


def _mark_max(ax, lv: Level, color: str, linestyle: str, label_prefix: str, is_support: bool):
    ax.axvline(lv.strike, color=color, linestyle=linestyle, linewidth=2, alpha=0.95)
    ax.annotate(
        f"{label_prefix}\n{lv.strike:.0f}",
        xy=(lv.strike, lv.pe_oi if is_support else lv.ce_oi),
        xytext=(8, 10 if is_support else -25),
        textcoords="offset points",
        color=color,
        fontsize=10,
        arrowprops=dict(arrowstyle="->", color=color),
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Overlay NSE option-chain support/resistance OI peaks.")
    ap.add_argument("--input1", required=True, help="First option-chain CSV/XLSX.")
    ap.add_argument("--input2", required=True, help="Second option-chain CSV/XLSX.")
    ap.add_argument("--output", required=True, help="Output PNG path.")
    ap.add_argument("--smooth-window", type=int, default=1, help="Rolling mean window (default: 1).")
    ap.add_argument("--top-n", type=int, default=3, help="Highlight top-N strikes (default: 3).")
    args = ap.parse_args()

    df1, strike_col1, ce_oi_col1, pe_oi_col1 = load_option_chain(args.input1)
    df2, strike_col2, ce_oi_col2, pe_oi_col2 = load_option_chain(args.input2)

    r1 = compute_support_resistance(
        df=df1,
        strike_col=strike_col1,
        ce_oi_col=ce_oi_col1,
        pe_oi_col=pe_oi_col1,
        top_n=args.top_n,
        smooth_window=args.smooth_window,
    )
    r2 = compute_support_resistance(
        df=df2,
        strike_col=strike_col2,
        ce_oi_col=ce_oi_col2,
        pe_oi_col=pe_oi_col2,
        top_n=args.top_n,
        smooth_window=args.smooth_window,
    )

    label1 = _label_from_path(args.input1)
    label2 = _label_from_path(args.input2)

    fig, ax = plt.subplots(figsize=(13, 7))

    # Put OI (support candidates)
    ax.plot(
        r1["data"]["strike"],
        r1["data"]["pe_oi_s"],
        color="green",
        linewidth=2,
        label=f"{label1} Put OI",
    )
    ax.plot(
        r2["data"]["strike"],
        r2["data"]["pe_oi_s"],
        color="dodgerblue",
        linestyle="-",
        linewidth=4,
        alpha=0.7,
        label=f"{label2} Put OI (blue, wider)",
    )

    # Call OI (resistance candidates)
    ax.plot(
        r1["data"]["strike"],
        r1["data"]["ce_oi_s"],
        color="red",
        linewidth=2,
        label=f"{label1} Call OI",
    )
    ax.plot(
        r2["data"]["strike"],
        r2["data"]["ce_oi_s"],
        color="orange",
        linestyle="-",
        linewidth=4,
        alpha=0.7,
        label=f"{label2} Call OI (orange, wider)",
    )

    # Mark max levels for both datasets
    _mark_max(
        ax,
        r1["max_support"],
        color="green",
        linestyle="-",
        label_prefix=f"Max Support ({label1})",
        is_support=True,
    )
    _mark_max(
        ax,
        r1["max_resistance"],
        color="red",
        linestyle="-",
        label_prefix=f"Max Resistance ({label1})",
        is_support=False,
    )
    _mark_max(
        ax,
        r2["max_support"],
        color="dodgerblue",
        linestyle="-",
        label_prefix=f"Max Support ({label2})",
        is_support=True,
    )
    _mark_max(
        ax,
        r2["max_resistance"],
        color="orange",
        linestyle="-",
        label_prefix=f"Max Resistance ({label2})",
        is_support=False,
    )

    # Optional: top-N peak markers (to show multiple likely levels)
    ax.scatter(
        [lv.strike for lv in r1["top_support"]],
        [lv.pe_oi for lv in r1["top_support"]],
        color="green",
        s=45,
        zorder=5,
        alpha=0.7,
    )
    ax.scatter(
        [lv.strike for lv in r2["top_support"]],
        [lv.pe_oi for lv in r2["top_support"]],
        color="dodgerblue",
        s=45,
        zorder=5,
        alpha=0.5,
    )
    ax.scatter(
        [lv.strike for lv in r1["top_resistance"]],
        [lv.ce_oi for lv in r1["top_resistance"]],
        color="red",
        s=45,
        zorder=5,
        alpha=0.7,
    )
    ax.scatter(
        [lv.strike for lv in r2["top_resistance"]],
        [lv.ce_oi for lv in r2["top_resistance"]],
        color="orange",
        s=45,
        zorder=5,
        alpha=0.5,
    )

    subtitle = f"(Smoothed OI: window={args.smooth_window})" if args.smooth_window and args.smooth_window > 1 else "(Raw OI)"
    ax.set_title(f"Overlay Support/Resistance (OI Peaks)\n{subtitle}")
    ax.set_xlabel("Strike Price")
    ax.set_ylabel("Open Interest (OI)")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="best", fontsize=9)
    fig.tight_layout()

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=160)
    plt.close(fig)

    m1s: Level = r1["max_support"]
    m1r: Level = r1["max_resistance"]
    m2s: Level = r2["max_support"]
    m2r: Level = r2["max_resistance"]

    print(f"[1] {label1} Max Support: strike={m1s.strike:.0f}, PE_OI={m1s.pe_oi:.0f}")
    print(f"[1] {label1} Max Resistance: strike={m1r.strike:.0f}, CE_OI={m1r.ce_oi:.0f}")
    print(f"[2] {label2} Max Support: strike={m2s.strike:.0f}, PE_OI={m2s.pe_oi:.0f}")
    print(f"[2] {label2} Max Resistance: strike={m2r.strike:.0f}, CE_OI={m2r.ce_oi:.0f}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

