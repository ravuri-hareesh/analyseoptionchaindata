import os
import logging
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Tuple, Optional, Union, Any

import pandas as pd
from utils import guess_columns, to_numeric

# --- LOGGING ---
logger = logging.getLogger("Data_Manager")

# --- PATH CONFIG ---
ROOT_DIR = Path(".")
INPUT_ROOT = ROOT_DIR / "input_file"
OUTPUT_ROOT = ROOT_DIR / "output"

def get_current_date_str() -> str:
    """Returns today's date in YYYY-MM-DD format."""
    return datetime.now().strftime("%Y-%m-%d")

def get_input_dir(date_str: Optional[str] = None) -> Path:
    """Gets or creates the input directory for a specific date."""
    if not date_str:
        date_str = get_current_date_str()
    path = INPUT_ROOT / date_str
    path.mkdir(parents=True, exist_ok=True)
    return path

def get_output_dir(date_str: Optional[str] = None) -> Path:
    """Gets or creates the output directory for a specific date."""
    if not date_str:
        date_str = get_current_date_str()
    path = OUTPUT_ROOT / date_str
    path.mkdir(parents=True, exist_ok=True)
    return path

def save_uploaded_file(uploaded_file: Any) -> Path:
    """Saves an uploaded file buffer to the input directory."""
    # Always save uploads to today's folder
    input_dir = get_input_dir() 
    file_path = input_dir / uploaded_file.name
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return file_path

def get_output_path(input_filename: Union[str, Path], date_str: Optional[str] = None, suffix: str = "_analysis.png") -> Path:
    """Names the output file based on the input filename and fixed suffix."""
    output_dir = get_output_dir(date_str)
    base_name = Path(input_filename).stem
    return output_dir / f"{base_name}{suffix}"

def get_available_dates() -> List[str]:
    """Retrieves all available trading dates from the filesystem."""
    dates = []
    if INPUT_ROOT.exists():
        for item in INPUT_ROOT.iterdir():
            if item.is_dir() and len(item.name) == 10:
                dates.append(item.name)
    
    today = get_current_date_str()
    if today not in dates:
        dates.append(today)
    
    return sorted(list(set(dates)), reverse=True)

def get_last_sync_info(date_str: str) -> Tuple[str, bool]:
    """Returns a simplified status label and recency flag for the latest sync."""
    input_dir = INPUT_ROOT / date_str
    if not input_dir.exists():
        return "No data", False
    
    files = list(input_dir.glob("*.csv")) + list(input_dir.glob("*.xlsx"))
    if not files:
        return "No data", False
    
    latest_file = max(files, key=lambda p: p.stat().st_mtime)
    mtime = datetime.fromtimestamp(latest_file.stat().st_mtime)
    
    time_label = mtime.strftime("%I:%M %p")
    is_recent = (datetime.now() - mtime) < timedelta(minutes=10)
    
    return time_label, is_recent

def load_option_chain(
    input_path: Union[str, Path],
    strike_col: Optional[str] = None,
    ce_oi_col: Optional[str] = None,
    pe_oi_col: Optional[str] = None,
    sheet_name: Union[int, str] = 0,
) -> Tuple[pd.DataFrame, str, str, str]:
    """
    Professionally loads and cleans an NSE option chain file.
    Automatically detects headers, handles HTML-masquerading-as-CSV, 
    and validates column structure.
    """
    path = Path(input_path)
    if not path.exists():
        raise FileNotFoundError(f"Sync file not found: {input_path}")

    suffix = path.suffix.lower()
    
    # --- CSV PROCESSING ---
    if suffix == ".csv":
        # 1. HTML Corruption Check
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                first_lines = "".join([f.readline() for _ in range(5)])
                if "<!DOCTYPE html" in first_lines.lower() or "<html" in first_lines.lower():
                     raise ValueError("⚠️ Corrupted Sync: File is HTML, not data. Please re-sync mirroring the API.")
        except Exception as e:
             if "Corrupted Sync" in str(e): raise e

        # 2. Header Auto-Detection (Fuzzy-Scan)
        # NSE CSVs often start with metadata rows. We find the row containing 
        # any known table-starter keywords in a case-insensitive way.
        header_row_index = 0
        keywords = ["STRIKE PRICE", "STRIKE", "UNDERLYING", "EXPIRY"]
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                for i, line in enumerate(f):
                    line_upper = line.upper()
                    if any(kw in line_upper for kw in keywords):
                        header_row_index = i
                        logger.info(f"Fuzzy header detected at row {i} for {path.name}")
                        break
                    if i > 30: break 
        except Exception as e:
             logger.debug(f"Header scan failed: {e}")
             header_row_index = 0

        # 3. Parsing
        try:
            df = pd.read_csv(path, header=header_row_index, on_bad_lines='skip')
        except Exception as e:
            raise ValueError(f"CSV Parse Error at {input_path.name}: {str(e)}")

    # --- EXCEL PROCESSING ---
    elif suffix in (".xlsx", ".xls"):
        try:
            df = pd.read_excel(path, sheet_name=sheet_name, engine="openpyxl")
        except Exception as e:
            raise ValueError(f"Excel Parse Error at {input_path.name}: {str(e)}")
    else:
        raise ValueError(f"Unsupported file format: {suffix}")

    # --- CLEANING & NORMALIZATION ---
    df = df.dropna(how="all").copy()
    df.columns = [str(c).replace("\n", " ").strip() for c in df.columns]

    # Resolve Columns
    strike_res, ce_res, pe_res = guess_columns(
        df, strike_col=strike_col, ce_oi_col=ce_oi_col, pe_oi_col=pe_oi_col
    )

    # Convert to Numeric
    df[strike_res] = to_numeric(df[strike_res])
    df[ce_res] = to_numeric(df[ce_res])
    df[pe_res] = to_numeric(df[pe_res])

    # Filter junk
    df = df.dropna(subset=[strike_res])
    df = df[(df[ce_res] > 0) | (df[pe_res] > 0)]
    
    return df, strike_res, ce_res, pe_res
