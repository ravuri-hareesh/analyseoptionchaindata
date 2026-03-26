from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import pandas as pd


@dataclass(frozen=True)
class Level:
    strike: float
    ce_oi: float
    pe_oi: float


def compute_support_resistance(
    df: pd.DataFrame,
    strike_col: str,
    ce_oi_col: str,
    pe_oi_col: str,
    top_n: int = 3,
    smooth_window: int = 1,
) -> Dict[str, Any]:
    """
    Compute support/resistance candidates using OI peaks:
    - Maximum support: strike with maximum PE open interest.
    - Maximum resistance: strike with maximum CE open interest.
    - Also returns top_n support/resistance strikes by PE/CE OI.

    Note: This is a simple, commonly used heuristic. Different traders use
    different formulas (e.g. OI change, PCR, etc.).
    """
    if top_n < 1:
        raise ValueError("--top-n must be >= 1")
    if smooth_window < 1:
        raise ValueError("--smooth-window must be >= 1")

    data = df[[strike_col, ce_oi_col, pe_oi_col]].copy()
    data = data.rename(columns={strike_col: "strike", ce_oi_col: "ce_oi", pe_oi_col: "pe_oi"})
    data = data.sort_values("strike").reset_index(drop=True)

    if smooth_window > 1 and len(data) >= smooth_window:
        # Rolling mean helps reduce noise without adding dependencies.
        data["ce_oi_s"] = data["ce_oi"].rolling(window=smooth_window, min_periods=1, center=True).mean()
        data["pe_oi_s"] = data["pe_oi"].rolling(window=smooth_window, min_periods=1, center=True).mean()
    else:
        data["ce_oi_s"] = data["ce_oi"]
        data["pe_oi_s"] = data["pe_oi"]

    # Max levels
    max_support_idx = int(data["pe_oi_s"].idxmax())
    max_resistance_idx = int(data["ce_oi_s"].idxmax())

    def to_level(i: int) -> Level:
        row = data.iloc[i]
        return Level(
            strike=float(row["strike"]),
            ce_oi=float(row["ce_oi"]),
            pe_oi=float(row["pe_oi"]),
        )

    max_support = to_level(max_support_idx)
    max_resistance = to_level(max_resistance_idx)

    # Top N by (smoothed) OI, reported with original OI values
    top_support_df = data.nlargest(top_n, "pe_oi_s")
    top_resistance_df = data.nlargest(top_n, "ce_oi_s")

    top_support: List[Level] = []
    top_resistance: List[Level] = []
    for _, r in top_support_df.iterrows():
        top_support.append(Level(strike=float(r["strike"]), ce_oi=float(r["ce_oi"]), pe_oi=float(r["pe_oi"])))
    for _, r in top_resistance_df.iterrows():
        top_resistance.append(
            Level(strike=float(r["strike"]), ce_oi=float(r["ce_oi"]), pe_oi=float(r["pe_oi"]))
        )

    # Make levels unique by strike (in case top_n overlaps max or duplicates)
    def unique_by_strike(levels: List[Level]) -> List[Level]:
        seen = set()
        out: List[Level] = []
        for lv in levels:
            k = lv.strike
            if k in seen:
                continue
            seen.add(k)
            out.append(lv)
        return out

    top_support = unique_by_strike(top_support)
    top_resistance = unique_by_strike(top_resistance)

    return {
        "data": data,
        "max_support": max_support,
        "max_resistance": max_resistance,
        "top_support": top_support,
        "top_resistance": top_resistance,
        "smooth_window": smooth_window,
    }

