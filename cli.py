from __future__ import annotations

import argparse
from pathlib import Path

from .analysis import compute_support_resistance
from .io import load_option_chain
from .plot import plot_support_resistance


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="nse-option-chain-graph",
        description="Read an NSE option-chain CSV/XLSX and plot support/resistance from OI peaks.",
    )

    p.add_argument("--input", "-i", required=True, help="Path to option-chain file (.csv or .xlsx).")
    p.add_argument("--output", "-o", default="output/support_resistance.png", help="Output image path (png).")
    p.add_argument("--show", action="store_true", help="Show the plot window.")

    # Column overrides (optional)
    p.add_argument("--strike-col", default=None, help="Exact strike column name in the file.")
    p.add_argument("--ce-oi-col", default=None, help="Exact CE OI column name in the file.")
    p.add_argument("--pe-oi-col", default=None, help="Exact PE OI column name in the file.")

    p.add_argument("--sheet", default=0, help="Excel sheet index/name (default: 0).")
    p.add_argument("--top-n", type=int, default=3, help="Highlight top N support/resistance strikes (default: 3).")
    p.add_argument("--smooth-window", type=int, default=1, help="Rolling mean window for smoothing (default: 1).")
    p.add_argument(
        "--title",
        default="NSE Option Chain: Support/Resistance (OI Peaks)",
        help="Plot title.",
    )

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    sheet_name = args.sheet
    # If sheet looks like an integer, treat it as an index
    if isinstance(sheet_name, str):
        try:
            sheet_name = int(sheet_name)
        except ValueError:
            pass

    df, strike_col, ce_oi_col, pe_oi_col = load_option_chain(
        input_path=args.input,
        strike_col=args.strike_col,
        ce_oi_col=args.ce_oi_col,
        pe_oi_col=args.pe_oi_col,
        sheet_name=sheet_name,
    )

    result = compute_support_resistance(
        df=df,
        strike_col=strike_col,
        ce_oi_col=ce_oi_col,
        pe_oi_col=pe_oi_col,
        top_n=args.top_n,
        smooth_window=args.smooth_window,
    )

    plot_support_resistance(
        analysis_result=result,
        output_path=args.output,
        show=args.show,
        title=args.title,
    )

    max_support = result["max_support"]
    max_resistance = result["max_resistance"]
    print(f"Max Support (PE OI peak): strike={max_support.strike:.0f}, PE_OI={max_support.pe_oi:.0f}")
    print(
        f"Max Resistance (CE OI peak): strike={max_resistance.strike:.0f}, CE_OI={max_resistance.ce_oi:.0f}"
    )
    print(f"Used columns: strike={strike_col!r}, ce_oi={ce_oi_col!r}, pe_oi={pe_oi_col!r}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

