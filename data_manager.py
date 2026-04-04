import os
import logging
import shutil
import re
import time
import json
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Tuple, Optional, Union, Any, Dict
from utils import guess_columns, to_numeric
from nsepython import nse_get_index_quote

# --- LOGGING ---
logger = logging.getLogger("Data_Manager")

# --- PATH CONFIG ---
ROOT_DIR = Path(".")
INPUT_ROOT = ROOT_DIR / "input_file"
OUTPUT_ROOT = ROOT_DIR / "output"

# --- DATE FORMAT CONFIG ---
APP_DATE_FORMAT = "%d-%m-%Y"
DB_DATE_FORMAT = "%Y-%m-%d" # Internal DB standard (MySQL/Mongo ISO)

def normalize_date_str(date_str: str) -> str:
    """
    Normalizes any date string (NSE format, ISO, etc.) to the centralized APP_DATE_FORMAT (DD-MM-YYYY).
    """
    if not date_str or not isinstance(date_str, str):
        return date_str
        
    date_str = date_str.strip()
    
    # Try multiple common formats
    formats = [
        APP_DATE_FORMAT,      # 07-04-2026
        "%Y-%m-%d",           # 2026-04-07
        "%d-%b-%Y",           # 07-Apr-2026
        "%d-%B-%Y",           # 07-April-2026
        "%Y/%m/%d",           # 2026/04/07
        "%d/%m/%Y",           # 07/04/2026
    ]
    
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime(APP_DATE_FORMAT)
        except ValueError:
            continue
            
    # If it's something like 07-APR-2026 (all caps), try case-insensitive
    try:
        dt = pd.to_datetime(date_str, dayfirst=True)
        if pd.notnull(dt):
            return dt.strftime(APP_DATE_FORMAT)
    except:
        pass
        
    return date_str

def get_current_date_str() -> str:
    """Returns today's date in the centralized APP_DATE_FORMAT."""
    return datetime.now().strftime(APP_DATE_FORMAT)

def extract_timestamp_from_filename(file_path: Union[str, Path]) -> datetime:
    """
    Robustly extracts HHMM from filenames like '0915.csv' or 'sv- 2026-04-02T131854.685.csv'.
    Skips patterns that look like years (2024-2030) or full dates.
    Falls back to file modification time if no valid HHMM is found.
    """
    stem = Path(file_path).stem
    
    # 1. Look for ISO-style 'T' separator: T131854
    iso_match = re.search(r'T(\d{2})(\d{2})', stem)
    if iso_match:
        try:
            hh, mm = int(iso_match.group(1)), int(iso_match.group(2))
            if 0 <= hh < 24 and 0 <= mm < 60:
                return datetime.strptime(f"{iso_match.group(1)}{iso_match.group(2)}", "%H%M")
        except: pass
        
    # 2. Look for clear HHMM patterns (skipping years)
    # We remove all YYYY-MM-DD or DD-MM-YYYY patterns first to avoid picking up days as times
    clean_stem = re.sub(r'\d{4}-\d{2}-\d{2}', ' ', stem)
    clean_stem = re.sub(r'\d{2}-\d{2}-\d{4}', ' ', clean_stem)
    clean_stem = re.sub(r'\d{2}-[A-Za-z]{3}-\d{4}', ' ', clean_stem) # 28-Apr-2026
    
    # Find all 4-digit sequences
    digits = re.findall(r'\d{4}', clean_stem)
    for d in digits:
        val = int(d)
        # Skip if it's a year-like number
        if 2020 <= val <= 2030:
            continue
        try:
            hh, mm = int(d[:2]), int(d[2:])
            if 0 <= hh < 24 and 0 <= mm < 60:
                return datetime.strptime(d, "%H%M")
        except: pass
                
    # 3. Final Fallback Catch-all: find any 4+ digits
    all_digits = re.sub(r'[^\d]', '', stem)
    if len(all_digits) >= 4:
        # Check starting digits or standard sync prefix
        # If it's something like 202604021318, we want the 1318 part (index 8:12)
        candidates = []
        if all_digits.startswith("202") and len(all_digits) >= 12:
            candidates.append(all_digits[8:12])
        candidates.append(all_digits[:4])
        
        for cand in candidates:
            try:
                hh, mm = int(cand[:2]), int(cand[2:])
                # STRICT VALIDATION: If hh >= 24 or mm >= 60, it's NOT a time
                if 0 <= hh < 24 and 0 <= mm < 60:
                    # Use strptime but wrap in try to catch "unconverted data remains"
                    return datetime.strptime(cand, "%H%M")
            except: continue
        
    # 4. Total Fallback: use file modification time
    try:
        return datetime.fromtimestamp(Path(file_path).stat().st_mtime)
    except:
        return datetime.now() # Absolute last resort

def _safe_merge_dirs(src: Path, dst: Path):
    """Recursively moves and merges directories and files."""
    if not src.exists(): return
    if not dst.exists():
        try:
            shutil.move(str(src), str(dst))
            return
        except Exception as e:
            logger.warning(f"Direct move failed from {src} to {dst}: {e}. Falling back to manual merge.")

    dst.mkdir(parents=True, exist_ok=True)
    for item in list(src.iterdir()):
        target = dst / item.name
        try:
            if item.is_dir():
                _safe_merge_dirs(item, target)
            else:
                if target.exists():
                    target = dst / f"{item.stem}_{int(time.time()*1000)}{item.suffix}"
                shutil.move(str(item), str(target))
        except Exception as ex:
            logger.error(f"Failed to move {item} to {target}: {ex}")
    
    try:
        src.rmdir()
    except Exception as ex:
        # On Windows/OneDrive, directories are often locked. Log and carry on.
        logger.debug(f"Could not remove empty dir {src}: {ex}")

# --- MIGRATION ENGINE ---
def migrate_legacy_data():
    """
    Standardizes structure to input_file/DD-MM-YYYY/DD-MM-YYYY/
    Recursively renames folders to adhere to the centralized DD-MM-YYYY format.
    """
    for root_dir in [INPUT_ROOT, OUTPUT_ROOT]:
        if not root_dir.exists():
            continue
            
        # Step 1: Normalize all first-level and second-level folders
        # We do this twice to ensure we catch everything after parent renames
        for _ in range(2):
            for date_item in list(root_dir.iterdir()):
                if not date_item.is_dir(): continue
                
                orig_date_name = date_item.name
                norm_date_name = normalize_date_str(orig_date_name)
                
                current_date_path = date_item
                if norm_date_name != orig_date_name:
                    target_date_path = root_dir / norm_date_name
                    _safe_merge_dirs(date_item, target_date_path)
                    current_date_path = target_date_path
                    logger.info(f"Refactored Market Date: {orig_date_name} -> {norm_date_name}")

                if current_date_path.exists():
                    for expiry_item in list(current_date_path.iterdir()):
                        if not expiry_item.is_dir(): continue
                        
                        orig_expiry_name = expiry_item.name
                        norm_expiry_name = normalize_date_str(orig_expiry_name)
                        
                        if norm_expiry_name != orig_expiry_name:
                            target_expiry_path = current_date_path / norm_expiry_name
                            _safe_merge_dirs(expiry_item, target_expiry_path)
                            logger.info(f"Refactored Expiry: {norm_date_name}/{orig_expiry_name} -> {norm_date_name}/{norm_expiry_name}")

        # Step 2: Rogue Expiry Detector (Handles Legacy Expiry/Date structures)
        for item in list(root_dir.iterdir()):
            if not item.is_dir(): continue
            name = item.name
            
            # If it's NOT a standardized date, it might be a rogue expiry folder
            if name != normalize_date_str(name):
                for sub in list(item.iterdir()):
                    if not sub.is_dir(): continue
                    try:
                        parsed_dt = pd.to_datetime(sub.name, dayfirst=True)
                        if pd.notnull(parsed_dt):
                            date_str = parsed_dt.strftime(APP_DATE_FORMAT)
                            expiry_norm = normalize_date_str(name)
                            
                            target_parent = root_dir / date_str
                            target_path = target_parent / expiry_norm
                            _safe_merge_dirs(sub, target_path)
                            logger.info(f"Corrected legacy structure: {name}/{sub.name} -> {date_str}/{expiry_norm}")
                    except: pass
                
                # Try cleanup
                try:
                    if not any(item.iterdir()):
                        item.rmdir()
                except: pass

# Run migration on import but catch all errors to prevent blocking the app
try:
    migrate_legacy_data()
except Exception as e:
    logger.error(f"Critical error during data migration: {e}")

def get_input_dir(expiry_date: str, date_str: Optional[str] = None) -> Path:
    """Gets or creates the nested input directory: input_file/DATE/EXPIRY/"""
    if not date_str:
        date_str = get_current_date_str()
    
    date_str = normalize_date_str(date_str)
    expiry_date = normalize_date_str(expiry_date)
    
    path = INPUT_ROOT / date_str / expiry_date
    path.mkdir(parents=True, exist_ok=True)
    return path

def get_output_dir(expiry_date: str, date_str: Optional[str] = None) -> Path:
    """Gets or creates the nested output directory: output/DATE/EXPIRY/"""
    if not date_str:
        date_str = get_current_date_str()
        
    date_str = normalize_date_str(date_str)
    expiry_date = normalize_date_str(expiry_date)
    
    path = OUTPUT_ROOT / date_str / expiry_date
    path.mkdir(parents=True, exist_ok=True)
    return path

def get_available_dates() -> List[str]:
    """Lists all available market analysis dates (top-level folders)."""
    dates = []
    if INPUT_ROOT.exists():
        for item in INPUT_ROOT.iterdir():
            if item.is_dir():
                if item.name == normalize_date_str(item.name):
                    dates.append(item.name)
    
    today = get_current_date_str()
    if today not in dates:
        dates.append(today)
    
    return sorted(list(set(dates)), reverse=True)

def get_available_expiries(date_str: str) -> List[str]:
    """Retrieves all target expiries available for a specific market date."""
    expiries = []
    date_root = INPUT_ROOT / date_str
    if date_root.exists():
        for item in date_root.iterdir():
            if item.is_dir():
                expiries.append(item.name)
    
    # Default if empty
    if not expiries and date_str == get_current_date_str():
        expiries.append(normalize_date_str("07-Apr-2026"))
    
    return sorted(expiries, reverse=True)

def get_latest_analysis_date(expiry: Optional[str] = None) -> str:
    """
    Returns the most recent market analysis date.
    If expiry is provided, returns the most recent date that has data for that expiry.
    """
    dates = get_available_dates()
    if not dates:
        return get_current_date_str()
        
    if expiry:
        # Narrow down to the most recent date that actually contains the target expiry
        expiry = normalize_date_str(expiry)
        for d in dates:
            if (INPUT_ROOT / d / expiry).exists():
                return d
    
    return dates[0]

def get_output_path(input_filename: Union[str, Path], expiry_date: str, date_str: Optional[str] = None, suffix: str = "_analysis.png") -> Path:
    """Names the output file based on the input filename and fixed suffix."""
    output_dir = get_output_dir(expiry_date, date_str)
    base_name = Path(input_filename).stem
    return output_dir / f"{base_name}{suffix}"

def discover_expiry_from_file(file_path_or_buffer: Any) -> str:
    """
    Discovers the expiry date from the file content (CSV or XLSX) or filename.
    Uses a 3-tier strategy for maximum accuracy during manual uploads.
    """
    import io
    
    # Tier 1: Filename Intelligence
    filename = ""
    if isinstance(file_path_or_buffer, (str, Path)):
        filename = Path(file_path_or_buffer).name
    elif hasattr(file_path_or_buffer, 'name'):
        filename = file_path_or_buffer.name
        
    if filename:
        # Search for DD-MMM-YYYY or DDMMMYYYY pattern in filename
        # Pattern example: 07-Apr-2026, 13Apr26, 07Apr26
        file_date_match = re.search(r'(\d{1,2})[-]?([A-Za-z]{3})[-]?(\d{2,4})', filename)
        if file_date_match:
            try:
                raw_extracted = f"{file_date_match.group(1)}-{file_date_match.group(2)}-{file_date_match.group(3)}"
                return normalize_date_str(raw_extracted)
            except: pass

    # Tier 2: Column Header and Deep Metadata Scan
    try:
        if isinstance(file_path_or_buffer, (str, Path)):
            suffix = Path(file_path_or_buffer).suffix.lower()
            if suffix == ".csv":
                df = pd.read_csv(file_path_or_buffer, nrows=100, on_bad_lines='skip', encoding='utf-8', errors='ignore')
            else:
                df = pd.read_excel(file_path_or_buffer, nrows=100)
        else:
            # Need to seek(0) if buffer was already read
            if hasattr(file_path_or_buffer, 'seek'):
                file_path_or_buffer.seek(0)
            content = file_path_or_buffer.getvalue()
            
            if getattr(file_path_or_buffer, 'name', '').lower().endswith('.csv'):
                df = pd.read_csv(io.BytesIO(content), nrows=100, on_bad_lines='skip', encoding='utf-8', errors='ignore')
            else:
                df = pd.read_excel(io.BytesIO(content), nrows=100)
        
        df.columns = [str(c).replace("\n", " ").strip().upper() for c in df.columns]
        
        # Step 2a: Explicit "EXPIRY" Column logic
        if "EXPIRY" in df.columns:
            val = df["EXPIRY"].dropna().iloc[0]
            if pd.notnull(val):
                return normalize_date_str(str(val).strip())
        
        # Step 2b: Deep Scan - Search all cells in the first 100 rows for a date-like string
        month_patterns = ["-JAN-", "-FEB-", "-MAR-", "-APR-", "-MAY-", "-JUN-", "-JUL-", "-AUG-", "-SEP-", "-OCT-", "-NOV-", "-DEC-"]
        for col in df.columns:
            # Convert series to string for regex search
            series_str = df[col].astype(str).str.upper()
            filtered = series_str[series_str.str.contains('|'.join(month_patterns), na=False)]
            if not filtered.empty:
                return normalize_date_str(filtered.iloc[0].strip())
                
        # Alternative: Search for DD-MM-YYYY or YYYY-MM-DD pattern in any cell
        for col in df.columns:
            for val in df[col].astype(str):
                # Simple DD-MM-YYYY or YYYY-MM-DD check
                if re.search(r'\d{2,4}[-/]\d{2}[-/]\d{2,4}', val):
                    return normalize_date_str(val.strip())

    except Exception as e:
        logger.warning(f"Expiry discovery failed: {e}")
    
    # Tier 3: Zero-Fallback Error Gate
    # NO HARDCODED DEFAULTS. If we reach here, we don't know the expiry.
    # We return the target_expiry provided by scraper if it exists, or raise error.
    raise ValueError("⚠️ CRITICAL: Could not determine Expiry Date from file content or filename. "
                     "Please ensure your file contains an 'EXPIRY' column or has the date in the filename (e.g., NIFTY_13-Apr-2026.csv).")

def save_sidecar_metadata(file_path: Path, metadata: Dict[str, Any]):
    """Saves non-destructive metadata to a .meta.json sidecar file."""
    meta_path = file_path.with_suffix(file_path.suffix + ".meta.json")
    try:
        with open(meta_path, "w") as f:
            json.dump(metadata, f, indent=4)
        logger.info(f"Saved sidecar metadata: {meta_path.name}")
    except Exception as e:
        logger.warning(f"Failed to save sidecar metadata: {e}")

def load_sidecar_metadata(file_path: Path) -> Optional[Dict[str, Any]]:
    """Loads metadata from a .meta.json sidecar file if it exists."""
    meta_path = file_path.with_suffix(file_path.suffix + ".meta.json")
    if meta_path.exists():
        try:
            with open(meta_path, "r") as f:
                return json.load(f)
        except: return None
    return None

def get_validated_spot(df: pd.DataFrame, file_path: Path, allow_api: bool = True) -> float:
    """
    Robustly determines spot price using API-first logic with retries,
    validated against the option chain's strike boundaries.
    """
    import re
    
    # Check sidecar first (Persistence Layer)
    sidecar = load_sidecar_metadata(file_path)
    if sidecar and "spot" in sidecar and sidecar["spot"] > 0:
        logger.info(f"Using spot from sidecar: {sidecar['spot']}")
        return float(sidecar["spot"])

    # Extract strike boundaries for validation
    strikes = pd.to_numeric(df.iloc[:, 0], errors='coerce').dropna() # Assume first col is strikes if unknown
    if strikes.empty:
        # Fallback to scanning columns for 'STRIKE'
        for col in df.columns:
            if "STRIKE" in str(col).upper():
                strikes = pd.to_numeric(df[col], errors='coerce').dropna()
                break
    
    s_min = strikes.min() if not strikes.empty else 0
    s_max = strikes.max() if not strikes.empty else 999999
    
    spot = 0
    api_data = None
    
    # Logic 1: API-First (with Retries)
    if allow_api:
        logger.info("Attempting NSE API spot retrieval...")
        for attempt in range(1, 4):
            try:
                # nse_get_index_quote is used as per user requirement for NIFTY 50 stability
                data = nse_get_index_quote("NIFTY 50")
                if isinstance(data, dict):
                    raw_val = data.get('last') or data.get('lastPrice') or data.get('underlyingValue')
                    if raw_val:
                        # Sanitize (remove commas)
                        clean_val = float(str(raw_val).replace(",", ""))
                        
                        # VALIDATION: Soft validation against strike boundaries
                        # If it's outside, we still accept it (API is truth) but log a warning.
                        if not (s_min <= clean_val <= s_max):
                             logger.warning(f"⚠️ API Spot {clean_val} is outside strike range ({s_min}-{s_max}). Option chain might be incomplete.")
                        
                        spot = clean_val
                        api_data = data # Store for metadata saving
                        logger.info(f"API Spot Accepted: {spot}")
                        break
                else:
                    logger.warning(f"API Attempt {attempt} returned non-dict: {type(data)}")
            except Exception as e:
                logger.warning(f"API Attempt {attempt} failed: {e}")
            
            if attempt < 3:
                time.sleep(2) # Brief backoff

    # Logic 2: Regex/File Fallback (if API fails or is disabled)
    if spot == 0:
        logger.info("Falling back to file-scanning regex for spot price...")
        # (Leveraging the already improved load_option_chain regex logic)
        # We manually check the DF columns first
        possible_spot_cols = ["SPOT PRICE", "UNDERLYING VALUE", "UNDERLYING", "SPOT", "VALUE"]
        for col in df.columns:
            col_upper = str(col).upper()
            if any(ps in col_upper for ps in possible_spot_cols):
                val = df[col].iloc[0]
                if pd.notnull(val):
                    try:
                        clean_val = float(str(val).replace(",", ""))
                        if clean_val > 0:
                            spot = clean_val
                            break
                    except: pass

    # Persistent Storage: Update sidecar if found
    if spot > 0:
        meta = sidecar or {}
        # Ensure 'spot' remains the primary mandatory field
        meta["spot"] = spot
        
        # If we have API data, merge it into the metadata
        if isinstance(api_data, dict):
            meta.update(api_data)
            
        save_sidecar_metadata(file_path, meta)

    return spot

def save_uploaded_file(uploaded_file: Any, date_str: Optional[str] = None) -> Path:
    """Saves an uploaded file to the discovered expiry nested directory."""
    expiry_date = discover_expiry_from_file(uploaded_file)
    input_dir = get_input_dir(expiry_date, date_str=date_str) 
    file_path = input_dir / uploaded_file.name
    
    # CRITICAL SAFETY: If the source and destination are the same, 
    # DO NOT open for writing yet, as it will truncate the file to 0 bytes 
    # before ‘MockUpload.getbuffer()’ can read it.
    if hasattr(uploaded_file, "path") and Path(uploaded_file.path).resolve() == file_path.resolve():
        logger.info(f"Skipping redundant write for {file_path.name} (Source == Destination)")
    else:
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
    
    from db_connector import OptEazyDB
    db = OptEazyDB()
    try:
        from analysis import compute_pcr, compute_support_resistance
        df, strike_col, ce_oi_col, pe_oi_col = load_option_chain(file_path)
        
        # USE THE NEW VALIDATED SPOT LOGIC
        spot = get_validated_spot(df, file_path, allow_api=True)
        
        # Multi-Band PCR (ATM-Centered) consistently with db_sync
        pcr_bands = {}
        strikes = sorted(df[strike_col].unique())
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
        sr_res = compute_support_resistance(df, strike_col, ce_oi_col, pe_oi_col)
        
        extracted_time = extract_timestamp_from_filename(file_path)
        try:
            timestamp = datetime.strptime(f"{normalize_date_str(date_str)} {extracted_time.strftime('%H%M')}", f"{APP_DATE_FORMAT} %H%M")
        except:
             timestamp = datetime.now()
             
        record = {
            "expiry": normalize_date_str(expiry_date),
            "Timestamp": timestamp,
            "Spot": spot,
            **pcr_bands,
            "PCR Overall": pcr_overall,
            "Major Support": sr_res["max_support"].strike,
            "Major Resistance": sr_res["max_resistance"].strike,
            "Immediate Support": sr_res["top_support"][0].strike if sr_res.get("top_support") else 0,
            "Immediate Resistance": sr_res["top_resistance"][0].strike if sr_res.get("top_resistance") else 0
        }
        # ... existing record building ...
        db.save_analysis_record(record)
        
        raw_meta = {
            "source": "upload",
            "file": uploaded_file.name,
            "type": "historic_csv"
        }
        db.save_raw_snapshot(raw_meta, normalize_date_str(expiry_date), timestamp.isoformat())
        return spot # Return the spot we saved
    except Exception as e:
        logger.error(f"Failed to sync uploaded file to databases: {e}")
        raise e # Re-raise for migration scripts to handle
    finally:
        db.close()
        
    return file_path

def get_last_sync_info(expiry_date: str, date_str: str) -> Tuple[str, bool]:
    """Returns a simplified status label and recency flag for the latest sync."""
    input_dir = INPUT_ROOT / normalize_date_str(date_str) / normalize_date_str(expiry_date)
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
    path = Path(input_path)
    if not path.exists():
        raise FileNotFoundError(f"Sync file not found: {input_path}")

    suffix = path.suffix.lower()
    
    if suffix == ".csv":
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                first_lines = "".join([f.readline() for _ in range(5)])
                if "<!DOCTYPE html" in first_lines.lower() or "<html" in first_lines.lower():
                     raise ValueError("⚠️ Corrupted Sync: File is HTML, not data.")
        except Exception as e:
             if "Corrupted Sync" in str(e): raise e

        header_row_index = 0
        keywords = ["STRIKE PRICE", "STRIKE", "UNDERLYING", "EXPIRY"]
        # Enhanced Spot Price Discovery for CSV
        underlying_val = None
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                for i, line in enumerate(f):
                    line_upper = line.upper()
                    # Check for common NSE header variations
                    if any(kw in line_upper for kw in ["UNDERLYING VALUE", "INDEX VALUE", "UNDERLYING INDEX"]):
                        # Find the first number after the keyword
                        # Handles formats like 22,513.70 or 22513.70
                        match = re.search(r"(\d{1,3}(?:,\d{3})*(?:\.\d+)?)", line)
                        if match:
                            underlying_val = float(match.group(1).replace(",", ""))
                            logger.info(f"Detected Spot via raw scan: {underlying_val}")
                    
                    if any(kw in line_upper for kw in keywords):
                        header_row_index = i
                        break
                    if i > 50: break 
        except Exception as e:
             logger.warning(f"Raw CSV spot/header scan failed: {e}")
             header_row_index = 0

        try:
            # Check file size first
            if path.stat().st_size == 0:
                raise ValueError(f"File {input_path.name} is empty (0 bytes).")
                
            df = pd.read_csv(path, header=header_row_index, on_bad_lines='skip', engine='c', low_memory=False)
            
            if df.empty or len(df.columns) == 0:
                 raise ValueError(f"No usable data columns found in {input_path.name}.")
                 
            if underlying_val and "Spot Price" not in df.columns:
                 df["Spot Price"] = underlying_val
        except Exception as e:
            raise ValueError(f"CSV Parse Error at {input_path.name}: {str(e)}")

    elif suffix in (".xlsx", ".xls"):
        try:
            df = pd.read_excel(path, sheet_name=sheet_name, engine="openpyxl")
        except Exception as e:
            raise ValueError(f"Excel Parse Error at {input_path.name}: {str(e)}")
    else:
        raise ValueError(f"Unsupported file format: {suffix}")

    df = df.dropna(how="all").copy()
    df.columns = [str(c).replace("\n", " ").strip() for c in df.columns]

    strike_res, ce_res, pe_res = guess_columns(
        df, strike_col=strike_col, ce_oi_col=ce_oi_col, pe_oi_col=pe_oi_col
    )

    df[strike_res] = to_numeric(df[strike_res])
    df[ce_res] = to_numeric(df[ce_res])
    df[pe_res] = to_numeric(df[pe_res])

    df = df.dropna(subset=[strike_res])
    df = df[(df[ce_res] > 0) | (df[pe_res] > 0)]
    
    return df, strike_res, ce_res, pe_res
