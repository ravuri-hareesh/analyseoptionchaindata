from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd

from utils import guess_columns, to_numeric


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
        # 0. Sanity Check: Is this actually HTML?
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                first_lines = "".join([f.readline() for _ in range(5)])
                if "<!DOCTYPE html" in first_lines.lower() or "<html" in first_lines.lower():
                     raise ValueError("⚠️ Corrupted Sync: This file is an HTML page, not data. Please perform a fresh cURL Sync.")
        except Exception as e:
             if "Corrupted Sync" in str(e): raise e

        # 1. High-Performance Pre-Scan to find the actual table header
        # NSE CSVs often start with metadata rows (e.g. Row 0 has only 1 column)
        # which crashes Pandas. We find the row containing "STRIKE PRICE".
        header_row_index = 0
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                for i, line in enumerate(f):
                    if "STRIKE PRICE" in line.upper():
                        header_row_index = i
                        break
                    if i > 20: break # Guardrail
        except:
             header_row_index = 0

        # 2. Dynamic Read with discovered header
        try:
            # We use on_bad_lines='skip' just in case there are footer metadata lines with fewer columns
            df = pd.read_csv(path, header=header_row_index, on_bad_lines='skip')
            df = df.dropna(how="all").copy()

            # Clean column names (NSE sometimes has spacing/newlines in names)
            df.columns = [str(c).replace("\n", " ").strip() for c in df.columns]

            strike_col_resolved, ce_oi_col_resolved, pe_oi_col_resolved = guess_columns(
                df,
                strike_col=strike_col,
                ce_oi_col=ce_oi_col,
                pe_oi_col=pe_oi_col,
            )

            df[strike_col_resolved] = to_numeric(df[strike_col_resolved])
            df[ce_oi_col_resolved] = to_numeric(df[ce_oi_col_resolved])
            df[pe_oi_col_resolved] = to_numeric(df[pe_oi_col_resolved])

            # Final filter: Drop rows where important levels are NaN (e.g. metadata footers)
            df = df.dropna(subset=[strike_col_resolved])
            # Only keep rows where at least one side has some activity to filter out headers/footers
            df = df[(df[ce_oi_col_resolved] > 0) | (df[pe_oi_col_resolved] > 0)]
            
            return df, strike_col_resolved, ce_oi_col_resolved, pe_oi_col_resolved
            
        except Exception as e:
            raise ValueError(f"Failed to parse NSE CSV at {input_path}. Error: {str(e)}")
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
