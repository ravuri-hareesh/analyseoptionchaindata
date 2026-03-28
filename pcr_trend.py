from __future__ import annotations

import argparse
import os
from pathlib import Path

import matplotlib.pyplot as plt

from analysis import compute_pcr
from data_io import load_option_chain


def main() -> int:
    p = argparse.ArgumentParser(description="Track PCR changes across multiple option chain files over time.")
    p.add_argument("--folder", required=True, help="Directory containing the option chain files.")
    p.add_argument("--output", default="output/pcr_trend.png", help="Output PNG path.")
    p.add_argument("--min-strike", type=float, default=None, help="Minimum strike for ranged PCR.")
    p.add_argument("--max-strike", type=float, default=None, help="Maximum strike for ranged PCR.")
    p.add_argument("--show", action="store_true", help="Show the plot window.")
    args = p.parse_args()

    folder_path = Path(args.folder)
    if not folder_path.is_dir():
        print(f"Error: Directory '{args.folder}' does not exist.")
        return 1

    # Find all csv/xlsx files and sort by modification time (oldest first)
    files = []
    for ext in ("*.csv", "*.xlsx"):
        files.extend(folder_path.glob(ext))
    
    if not files:
        print(f"No CSV or Excel files found in '{args.folder}'.")
        return 0

    files.sort(key=lambda f: os.path.getmtime(f))

    labels = []
    overall_pcrs = []
    ranged_pcrs = []

    for fpath in files:
        try:
            df, strike_col, ce_oi_col, pe_oi_col = load_option_chain(str(fpath))
            result = compute_pcr(
                df=df,
                strike_col=strike_col,
                ce_oi_col=ce_oi_col,
                pe_oi_col=pe_oi_col,
                min_strike=args.min_strike,
                max_strike=args.max_strike,
            )
            labels.append(fpath.name)
            overall_pcrs.append(result["overall_pcr"])
            if "ranged_pcr" in result:
                ranged_pcrs.append(result["ranged_pcr"])
        except Exception as e:
            print(f"Warning: Failed to process {fpath.name}: {e}")

    if not labels:
        print("No valid files processed.")
        return 1

    # Plotting
    fig, ax = plt.subplots(figsize=(10, 6))
    
    x_pos = list(range(len(labels)))
    ax.plot(x_pos, overall_pcrs, marker="o", color="blue", linewidth=2, label="Overall PCR")
    
    if args.min_strike is not None or args.max_strike is not None:
        if len(ranged_pcrs) == len(labels):
            ax.plot(x_pos, ranged_pcrs, marker="o", color="orange", linewidth=2, linestyle="--", label="Ranged PCR")
    
    ax.set_xticks(x_pos)
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=9)
    
    ax.set_title("Put-Call Ratio (PCR) Trend")
    ax.set_xlabel("Files (Chronological)")
    ax.set_ylabel("PCR (Put OI / Call OI)")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best")
    
    # Draw horizontal line at PCR = 1.0 (neutral) for reference
    ax.axhline(1.0, color="red", linestyle=":", alpha=0.7)

    fig.tight_layout()

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=160)
    
    if args.show:
        plt.show()
    plt.close(fig)

    print(f"Successfully processed {len(labels)} files.")
    print(f"PCR trend plot saved to {args.output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
