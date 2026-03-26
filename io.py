from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd

from .utils import guess_columns, to_numeric


def load_option_chain(
    input_path: str,
    strike_col: Optional[str] = None,
    ce_oi_col: Optional[str] = None,
    pe_oi_col: Optional[str] = None,
    sheet_name: int | str = 0,
) -> tuple[pd.DataFrame, str, str, str]:
    """
    Load an option-chain table and return:
    - cleaned df
    - (strike_col, ce_oi_col, pe_oi_col) resolved from guessing or CLI overrides
    """
    path = Path(input_path)
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    suffix = path.suffix.lower()
    if suffix == ".csv":
        # Some NSE exports have a "CALLS/PUTS" 2-line header.
        # Trying both `header=0` and `header=1` makes the loader robust.
        header_attempts = [0, 1]
        last_err: Exception | None = None
        for header in header_attempts:
            try:
                df = pd.read_csv(path, header=header)
                df = df.dropna(how="all").copy()

                strike_col_resolved, ce_oi_col_resolved, pe_oi_col_resolved = guess_columns(
                    df,
                    strike_col=strike_col,
                    ce_oi_col=ce_oi_col,
                    pe_oi_col=pe_oi_col,
                )

                df[strike_col_resolved] = to_numeric(df[strike_col_resolved])
                df[ce_oi_col_resolved] = to_numeric(df[ce_oi_col_resolved])
                df[pe_oi_col_resolved] = to_numeric(df[pe_oi_col_resolved])

                df = df.dropna(subset=[strike_col_resolved, ce_oi_col_resolved, pe_oi_col_resolved])
                return df, strike_col_resolved, ce_oi_col_resolved, pe_oi_col_resolved
            except Exception as e:  # noqa: BLE001 - we want to try next header attempt
                last_err = e

        raise ValueError(f"Failed to parse CSV columns from {input_path}. Last error: {last_err}")
    elif suffix in (".xlsx", ".xls"):
        df = pd.read_excel(path, sheet_name=sheet_name, engine="openpyxl")
    else:
        raise ValueError(f"Unsupported file type {suffix!r}. Use .csv or .xlsx.")

    # Drop empty rows that sometimes appear in NSE exports
    df = df.dropna(how="all").copy()

    strike_col_resolved, ce_oi_col_resolved, pe_oi_col_resolved = guess_columns(
        df,
        strike_col=strike_col,
        ce_oi_col=ce_oi_col,
        pe_oi_col=pe_oi_col,
    )

    df[strike_col_resolved] = to_numeric(df[strike_col_resolved])
    df[ce_oi_col_resolved] = to_numeric(df[ce_oi_col_resolved])
    df[pe_oi_col_resolved] = to_numeric(df[pe_oi_col_resolved])

    df = df.dropna(subset=[strike_col_resolved, ce_oi_col_resolved, pe_oi_col_resolved])

    return df, strike_col_resolved, ce_oi_col_resolved, pe_oi_col_resolved

