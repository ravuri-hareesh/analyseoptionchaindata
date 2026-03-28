from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from pathlib import Path

import pandas as pd


@dataclass(frozen=True)
class Level:
    """
    Represents a strike price and its corresponding Call and Put Open Interest.
    Used for Support and Resistance calculations.
    """
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


def compute_pcr(
    df: pd.DataFrame,
    strike_col: str,
    ce_oi_col: str,
    pe_oi_col: str,
    min_strike: Optional[float] = None,
    max_strike: Optional[float] = None,
) -> Dict[str, float]:
    """
    Compute Put-Call Ratio (PCR).
    Returns a dict with 'overall_pcr' and 'ranged_pcr' (if range provided).
    PCR = Sum(PE_OI) / Sum(CE_OI)
    """
    data = df[[strike_col, ce_oi_col, pe_oi_col]].copy()
    data = data.rename(columns={strike_col: "strike", ce_oi_col: "ce_oi", pe_oi_col: "pe_oi"})
    data["ce_oi"] = pd.to_numeric(data["ce_oi"], errors="coerce").fillna(0)
    data["pe_oi"] = pd.to_numeric(data["pe_oi"], errors="coerce").fillna(0)

    total_ce = data["ce_oi"].sum()
    total_pe = data["pe_oi"].sum()
    overall_pcr = float(total_pe / total_ce) if total_ce > 0 else 0.0

    result = {"overall_pcr": overall_pcr}

    if min_strike is not None or max_strike is not None:
        mask = pd.Series(True, index=data.index)
        if min_strike is not None:
            mask = mask & (data["strike"] >= min_strike)
        if max_strike is not None:
            mask = mask & (data["strike"] <= max_strike)
        
        ranged_data = data[mask]
        ranged_ce = ranged_data["ce_oi"].sum()
        ranged_pe = ranged_data["pe_oi"].sum()
        result["ranged_pcr"] = float(ranged_pe / ranged_ce) if ranged_ce > 0 else 0.0

    return result


def compute_evolution_data(
    file_paths: List[str],
    load_func,
) -> pd.DataFrame:
    """
    Analyzes a sequence of files to track levels over time.
    Returns a DataFrame with columns: [Timestamp, Spot, Major Support, Major Resistance, Immediate Support, Immediate Resistance, PCR]
    """
    records = []
    
    for fpath in file_paths:
        try:
            df, strike_col, ce_oi_col, pe_oi_col = load_func(str(fpath))
            
            # 1. Basic Support/Resistance/Smoothed Data
            res = compute_support_resistance(df, strike_col, ce_oi_col, pe_oi_col, top_n=5, smooth_window=3)
            data = res["data"]
            
            # 2. PCR
            pcr_res = compute_pcr(df, strike_col, ce_oi_col, pe_oi_col)
            pcr_overall = pcr_res["overall_pcr"]
            
            # 3. Estimate Spot (ATM): Where CE and PE OI are balanced
            data["oi_sum"] = data["ce_oi_s"] + data["pe_oi_s"]
            data["oi_diff_ratio"] = (data["ce_oi_s"] - data["pe_oi_s"]).abs() / (data["oi_sum"] + 1)
            # Find strike that is "At The Money"
            spot_row = data.nsmallest(1, "oi_diff_ratio").iloc[0]
            spot = float(spot_row["strike"])
            
            # 2b. Ranged PCR (±2% of Spot)
            pcr_ranged_res = compute_pcr(df, strike_col, ce_oi_col, pe_oi_col, 
                                         min_strike=spot * 0.98, max_strike=spot * 1.02)
            pcr_ranged = pcr_ranged_res["ranged_pcr"]
            
            # 4. Major Levels
            max_s = res["max_support"].strike
            max_r = res["max_resistance"].strike
            
            # 5. Immediate Levels (peaks closest to spot)
            imm_s_df = data[data["strike"] < spot].nlargest(1, "pe_oi_s")
            imm_r_df = data[data["strike"] > spot].nlargest(1, "ce_oi_s")
            
            imm_s = float(imm_s_df.iloc[0]["strike"]) if not imm_s_df.empty else max_s
            imm_r = float(imm_r_df.iloc[0]["strike"]) if not imm_r_df.empty else max_r
            
            # 6. Timestamp from file name or modification time
            f_path_obj = Path(fpath)
            ts_label = f_path_obj.stem
            
            # If name is 4 digits (HHMM), format as HH:MM
            if len(ts_label) == 4 and ts_label.isdigit():
                ts_label = f"{ts_label[:2]}:{ts_label[2:]}"
            # If name is 6 digits (HHMMSS), format as HH:MM:SS
            elif len(ts_label) == 6 and ts_label.isdigit():
                ts_label = f"{ts_label[:2]}:{ts_label[2:4]}:{ts_label[4:]}"
                
            records.append({
                "Timestamp": ts_label,
                "Spot": spot,
                "Major Support": max_s,
                "Major Resistance": max_r,
                "Immediate Support": imm_s,
                "Immediate Resistance": imm_r,
                "PCR Overall": pcr_overall,
                "PCR Ranged (2%)": pcr_ranged
            })
        except Exception:
            continue
            
    if not records:
        return pd.DataFrame()
    return pd.DataFrame(records).sort_values("Timestamp")
