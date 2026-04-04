from __future__ import annotations

import re
from typing import Optional, Tuple

import pandas as pd


def _norm_col(s: str) -> str:
    """
    Normalize a column name so we can match variants like:
    - "Strike Price" vs "strikePrice"
    - "CE OI" vs "Call Open Interest"
    """
    s = str(s)
    s = s.strip().lower()
    s = re.sub(r"[\s_\-]+", "", s)
    return s


def _pick_col(df: pd.DataFrame, predicate) -> Optional[str]:
    for c in df.columns:
        if predicate(c):
            return c
    return None


def guess_columns(
    df: pd.DataFrame,
    strike_col: Optional[str] = None,
    ce_oi_col: Optional[str] = None,
    pe_oi_col: Optional[str] = None,
) -> Tuple[str, str, str]:
    """
    Guess the (strike, call OI, put OI) column names from common NSE exports.
    """
    cols = list(df.columns)
    if not cols:
        raise ValueError("Input file has no columns.")

    # Convert columns to standardized forms for matching
    cols_norm = [_norm_col(c) for c in df.columns]
    
    # 1. GUESS STRIKE
    if strike_col is None:
        # Priority: Exact match, then fuzzy
        for kw in ["strikeprice", "strike"]:
            if kw in cols_norm:
                strike_col = df.columns[cols_norm.index(kw)]
                break
        if strike_col is None:
            strike_col = _pick_col(df, lambda c: "strike" in _norm_col(c))

    # 2. GUESS CE / CALL OI
    if ce_oi_col is None:
        # Priority: Normalized match (CE OI, CALL OPEN INTEREST)
        ce_oi_col = _pick_col(df, lambda c: ("ce" in _norm_col(c) or "call" in _norm_col(c)) and "oi" in _norm_col(c))
        # Fallback: Just "OI" if it appears before PE (NSE Standard)
        if ce_oi_col is None and "oi" in cols_norm:
            ce_oi_col = df.columns[cols_norm.index("oi")]

    # 3. GUESS PE / PUT OI
    if pe_oi_col is None:
        # Priority 1: "OI.1" (Pandas rename of the second 'OI' column in most NSE exports)
        if "OI.1" in df.columns:
            pe_oi_col = "OI.1"
        # Priority 2: Fuzzy match
        if pe_oi_col is None:
            pe_oi_col = _pick_col(df, lambda c: ("pe" in _norm_col(c) or "put" in _norm_col(c)) and "oi" in _norm_col(c) and c != ce_oi_col)
        # Priority 3: Second "OI" if first was CE
        if pe_oi_col is None and cols_norm.count("oi") > 1:
            indices = [i for i, x in enumerate(cols_norm) if x == "oi"]
            pe_oi_col = df.columns[indices[-1]]

    # 4. LAST RESORT FUZZY ALL
    if ce_oi_col is None:
        ce_oi_col = _pick_col(df, lambda c: "openinterest" in _norm_col(c))
    if pe_oi_col is None:
        pe_oi_col = _pick_col(df, lambda c: "openinterest" in _norm_col(c) and c != ce_oi_col)

    missing = []
    if strike_col is None: missing.append("strike")
    if ce_oi_col is None: missing.append("ce_oi")
    if pe_oi_col is None: missing.append("pe_oi")

    if missing:
        raise ValueError(
            f"Could not guess required columns: {', '.join(missing)}.\n"
            f"Available columns: {cols[:10]}..."
        )

    return strike_col, ce_oi_col, pe_oi_col


def to_numeric(series: pd.Series) -> pd.Series:
    """
    Convert a column to numeric, handling strings with commas/spaces.
    """
    return pd.to_numeric(series.astype(str).str.replace(",", "").str.strip(), errors="coerce")

