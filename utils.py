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

    If you know the exact column names, prefer passing them via CLI flags.
    """
    cols = list(df.columns)
    if not cols:
        raise ValueError("Input file has no columns.")

    # Special-case: some NSE option-chain CSV exports come out with flat columns like:
    #   STRIKE, OI (Calls), OI.1 (Puts)
    if strike_col is None and ce_oi_col is None and pe_oi_col is None:
        if "STRIKE" in df.columns and "OI" in df.columns and "OI.1" in df.columns:
            return "STRIKE", "OI", "OI.1"

    if strike_col is not None:
        if strike_col not in df.columns:
            raise ValueError(f"strike column not found: {strike_col!r}")
    if ce_oi_col is not None:
        if ce_oi_col not in df.columns:
            raise ValueError(f"CE OI column not found: {ce_oi_col!r}")
    if pe_oi_col is not None:
        if pe_oi_col not in df.columns:
            raise ValueError(f"PE OI column not found: {pe_oi_col!r}")

    # Strike
    if strike_col is None:
        strike_col = _pick_col(
            df,
            lambda c: "strike" in _norm_col(c),
        )

    # CE/PE OI
    if ce_oi_col is None:
        # Most common: CE OI / Call OI
        ce_oi_col = _pick_col(
            df,
            lambda c: ("ce" in _norm_col(c) and "oi" in _norm_col(c))
            or ("call" in _norm_col(c) and "oi" in _norm_col(c)),
        )

    if pe_oi_col is None:
        pe_oi_col = _pick_col(
            df,
            lambda c: ("pe" in _norm_col(c) and "oi" in _norm_col(c))
            or ("put" in _norm_col(c) and "oi" in _norm_col(c)),
        )

    # Last resort: explicit "Open Interest" without CE/PE then split by "Call"/"Put"
    if ce_oi_col is None:
        ce_oi_col = _pick_col(
            df,
            lambda c: "openinterest" in _norm_col(c) and ("call" in _norm_col(c) or "ce" in _norm_col(c)),
        )
    if pe_oi_col is None:
        pe_oi_col = _pick_col(
            df,
            lambda c: "openinterest" in _norm_col(c) and ("put" in _norm_col(c) or "pe" in _norm_col(c)),
        )

    missing = []
    if strike_col is None:
        missing.append("strike")
    if ce_oi_col is None:
        missing.append("ce_oi")
    if pe_oi_col is None:
        missing.append("pe_oi")

    if missing:
        raise ValueError(
            "Could not guess required columns: "
            + ", ".join(missing)
            + ".\n"
            + "Tip: pass --strike-col, --ce-oi-col, --pe-oi-col with the exact names."
        )

    return strike_col, ce_oi_col, pe_oi_col


def to_numeric(series: pd.Series) -> pd.Series:
    """
    Convert a column to numeric, handling strings with commas/spaces.
    """
    return pd.to_numeric(series.astype(str).str.replace(",", "").str.strip(), errors="coerce")

