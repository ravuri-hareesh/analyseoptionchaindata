from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from pathlib import Path
import re
import concurrent.futures
from datetime import datetime
import pandas as pd

# --- PERFORMANCE CACHE (HOT-LOAD LAYER) ---
_EVOLUTION_CACHE: Dict[str, Dict[str, Any]] = {}

def clear_evolution_cache():
    """Explicitly purges the hot-load analysis cache."""
    global _EVOLUTION_CACHE
    _EVOLUTION_CACHE = {}
    return True


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
    ce_col: str,
    pe_col: str,
    min_strike: Optional[float] = None,
    max_strike: Optional[float] = None,
) -> Dict[str, float]:
    """
    Compute Put-Call Ratio (PCR).
    Returns a dict with 'overall_pcr' and 'ranged_pcr' (if range provided).
    PCR = Sum(PE_OI) / Sum(CE_OI)
    """
    data = df[[strike_col, ce_col, pe_col]].copy()
    data = data.rename(columns={strike_col: "strike", ce_col: "ce_oi", pe_col: "pe_oi"})
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


def _process_single_file(fpath: str, load_func) -> Optional[Dict[str, Any]]:
    """Helper for parallel processing of a single option chain file."""
    try:
        f_path_obj = Path(fpath)
        mtime = f_path_obj.stat().st_mtime
        # Versioning the cache key to force schema updates (PCR Overall fix)
        cache_key = f"{fpath}_{mtime}_v2"
        
        # 1. Hot-Cache Lookup (Bypass I/O and CPU if file hasn't changed)
        if cache_key in _EVOLUTION_CACHE:
            return _EVOLUTION_CACHE[cache_key]
            
        # 2. Data Loading
        df, strike_col, ce_oi_col, pe_oi_col = load_func(str(fpath))
        if df.empty: return None
        
        # Use a copy to prevent mutation issues in multithreaded context
        df = df.copy()

        # 3. Support/Resistance logic
        res = compute_support_resistance(df, strike_col, ce_oi_col, pe_oi_col, top_n=5, smooth_window=3)
        data = res["data"]
        
        # 4. Precision Spot Detection (Consistent with sidecar logic)
        from data_manager import get_validated_spot
        spot = get_validated_spot(df, f_path_obj, allow_api=False) # Dashboard never calls API during processing
        
        if spot == 0:
             try:
                 cols = list(df.columns)
                 ltp_indices = [i for i, c in enumerate(cols) if "LTP" in str(c).upper() or "LAST" in str(c).upper()]
                 if len(ltp_indices) >= 2:
                     ce_ltp = cols[ltp_indices[0]] 
                     pe_ltp = cols[ltp_indices[-1]] 
                     
                     from utils import to_numeric
                     temp = df[[strike_col, ce_ltp, pe_ltp]].copy()
                     temp[strike_col] = to_numeric(temp[strike_col])
                     temp[ce_ltp] = to_numeric(temp[ce_ltp])
                     temp[pe_ltp] = to_numeric(temp[pe_ltp])
                     
                     # Liquidity Gate: Must have active trades on both sides
                     temp = temp[(temp[ce_ltp] > 0) & (temp[pe_ltp] > 0)]
                     
                     if not temp.empty:
                         temp["cp_diff"] = (temp[ce_ltp] - temp[pe_ltp]).abs()
                         idx = temp["cp_diff"].idxmin()
                         atm_row = temp.loc[idx]
                         spot = float(atm_row[strike_col] + (atm_row[ce_ltp] - atm_row[pe_ltp]))
             except: pass

        if spot == 0:
            data["oi_sum"] = data["ce_oi_s"] + data["pe_oi_s"]
            data["oi_diff_ratio"] = (data["ce_oi_s"] - data["pe_oi_s"]).abs() / (data["oi_sum"] + 1)
            spot_row = data.nsmallest(1, "oi_diff_ratio").iloc[0]
            spot = float(spot_row["strike"])
        
        # 5. Multi-Band PCR (ATM-Centered)
        pcr_bands = {}
        strikes = sorted(data["strike"].unique())
        interval = 50
        if len(strikes) > 1:
            interval = strikes[1] - strikes[0]
        atm_strike = round(spot / interval) * interval
        
        for i in range(1, 6):
            range_pts = spot * (i / 100.0)
            num_strikes = round(range_pts / interval)
            if num_strikes == 0 and i > 0: num_strikes = 1
            p_res = compute_pcr(df, strike_col, ce_oi_col, pe_oi_col, 
                                min_strike=atm_strike - (num_strikes * interval), 
                                max_strike=atm_strike + (num_strikes * interval))
            pcr_bands[f"PCR Ranged ({i}%)"] = p_res["ranged_pcr"]
        
        pcr_overall = compute_pcr(df, strike_col, ce_oi_col, pe_oi_col)["overall_pcr"]

        # 6. Levels
        max_s = res["max_support"].strike
        max_s_oi = res["max_support"].pe_oi
        max_r = res["max_resistance"].strike
        max_r_oi = res["max_resistance"].ce_oi
        
        imm_s_df = data[data["strike"] < spot].nlargest(1, "pe_oi_s")
        imm_r_df = data[data["strike"] > spot].nlargest(1, "ce_oi_s")
        imm_s = float(imm_s_df.iloc[0]["strike"]) if not imm_s_df.empty else max_s
        imm_s_oi = float(imm_s_df.iloc[0]["pe_oi_s"]) if not imm_s_df.empty else max_s_oi
        imm_r = float(imm_r_df.iloc[0]["strike"]) if not imm_r_df.empty else max_r
        imm_r_oi = float(imm_r_df.iloc[0]["ce_oi_s"]) if not imm_r_df.empty else max_r_oi

        # 7. Metadata Timestamp Extraction
        ts_label = f_path_obj.stem
        file_ts = None
        try:
            with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                for _ in range(15):
                    line = f.readline()
                    if not line: break
                    # Robust search for time in various formats (9:15, 09:15, 15:30:04)
                    match = re.search(r"(\d{1,2}:\d{2}(?::\d{2})?)", line)
                    if match:
                        parts = match.group(1).split(":")
                        # Ensure HH:MM zero-padding for alphabetical sorting
                        file_ts = f"{int(parts[0]):02d}:{parts[1]}"
                        break
        except: pass
        
        if file_ts:
            ts_label = file_ts
        else:
            time_match = re.search(r"T(\d{2})(\d{2})", ts_label)
            if not time_match:
                all_clusters = re.findall(r"(\d{4})", ts_label)
                if all_clusters:
                    valid = [c for c in all_clusters if not c.startswith("20")]
                    tm_val = valid[-1] if valid else all_clusters[-1]
                    ts_label = f"{tm_val[:2]}:{tm_val[2:]}"
            if time_match:
                ts_label = f"{time_match.group(1)}:{time_match.group(2)}"
            
            if ":" not in ts_label or ts_label == "20:26":
                 mtime_dt = datetime.fromtimestamp(mtime)
                 ts_label = mtime_dt.strftime("%H:%M")

        record = {
            "Timestamp": ts_label,
            "Spot": spot,
            "Major Support": max_s, "Major Support OI": max_s_oi,
            "Major Resistance": max_r, "Major Resistance OI": max_r_oi,
            "Immediate Support": imm_s, "Immediate Support OI": imm_s_oi,
            "Immediate Resistance": imm_r, "Immediate Resistance OI": imm_r_oi,
            "PCR Overall": pcr_overall,
            **pcr_bands
        }
        
        # Update Cache
        _EVOLUTION_CACHE[cache_key] = record
        return record

    except Exception:
        return None

def compute_evolution_data(
    file_paths: List[str],
    load_func,
) -> pd.DataFrame:
    """
    Optimized Parallel Evolution Logic.
    Processes multiple option chain files using multi-threading and per-file results caching.
    """
    records = []
    
    # Use ThreadPoolExecutor for parallel scanning and processing
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future_to_path = {executor.submit(_process_single_file, fpath, load_func): fpath for fpath in file_paths}
        
        for future in concurrent.futures.as_completed(future_to_path):
            result = future.result()
            if result:
                records.append(result)

    if not records:
        return pd.DataFrame()
    
    return pd.DataFrame(records).sort_values("Timestamp")
