import os
import logging
from pathlib import Path
from datetime import datetime
import pandas as pd
import time
import re
from db_connector import OptEazyDB
from data_manager import load_option_chain, INPUT_ROOT, APP_DATE_FORMAT, normalize_date_str, extract_timestamp_from_filename
from analysis import compute_pcr, compute_support_resistance

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DB_Sync")

def sync_all_files(reset=False):
    """
    Scans the input_file directory and populates the databases.
    Structure: input_file / ANY_DATE / ANY_EXPIRY / FILE
    """
    db = OptEazyDB()
    if not (db.connect_mysql() and db.connect_mongo()):
        logger.error("Could not connect to databases. Aborting sync.")
        return

    if reset:
        logger.info("Resetting databases before sync...")
        db.reset_databases()

    logger.info("Starting Bulk Sync...")
    
    if not INPUT_ROOT.exists():
        logger.error(f"Input root {INPUT_ROOT} does not exist.")
        return

    processed_count = 0
    error_count = 0

    # Walk through the entire input_file directory to find all CSVs
    for root, dirs, files in os.walk(INPUT_ROOT):
        root_path = Path(root)
        
        # We expect files to be at least 2 levels deep: input_file/DATE/EXPIRY/FILE.csv
        # or even 1 level if legacy. We'll try to infer DATE and EXPIRY from the path.
        relative_path = root_path.relative_to(INPUT_ROOT)
        parts = relative_path.parts
        
        if not parts: continue # Skip root itself
        
        # Infer Market Date (usually first part)
        date_str = normalize_date_str(parts[0])
        
        # Infer Expiry (usually second part or same as date if 1 level)
        expiry_date = normalize_date_str(parts[1]) if len(parts) > 1 else date_str
        
        for file in files:
            if not file.endswith(".csv"): continue
            
            file_path = root_path / file
            try:
                # 1. Load Data
                df, strike_col, ce_oi_col, pe_oi_col = load_option_chain(file_path)
                if df.empty: continue
                
                # 2. Extract Metrics (more robust detection)
                spot = 0
                possible_spot_cols = ["Spot Price", "Underlying Value", "Underlying", "spot", "value"]
                for col in df.columns:
                    if any(ps.lower() in col.lower() for ps in possible_spot_cols):
                        val = df[col].iloc[0]
                        if pd.notnull(val) and val > 0:
                            spot = float(val)
                            break
                
                # Manual fallback for spot if still 0
                if spot == 0:
                    try:
                        # Try to find atmospheric center from analysis.py style logic if possible
                        # but for sync let's just use the median strike if nothing else works
                        spot = df[strike_col].median()
                    except: pass
                
                if spot == 0:
                    logger.warning(f"Skipping {file_path}: Could not determine spot price.")
                    continue

                # PCR Bands
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
                
                # S/R
                sr_res = compute_support_resistance(df, strike_col, ce_oi_col, pe_oi_col, top_n=5, smooth_window=3)
                
                # 3. Prepare Timestamp
                extracted_time = extract_timestamp_from_filename(file_path)
                time_str = extracted_time.strftime("%H%M")
                
                # Parse date_str carefully
                # We expect date_str to be in APP_DATE_FORMAT after migration
                try:
                    # Try centralized format first
                    market_dt_obj = datetime.strptime(date_str, APP_DATE_FORMAT)
                    market_dt_iso = market_dt_obj.strftime("%Y-%m-%d")
                    timestamp = datetime.strptime(f"{market_dt_iso} {time_str}", "%Y-%m-%d %H%M")
                except:
                    try:
                        # Fallback to general parsing
                        market_dt_obj = pd.to_datetime(date_str, dayfirst=True)
                        market_dt_iso = market_dt_obj.strftime("%Y-%m-%d")
                        timestamp = datetime.strptime(f"{market_dt_iso} {time_str}", "%Y-%m-%d %H%M")
                    except:
                        # Fallback to file modification time
                        timestamp = datetime.fromtimestamp(file_path.stat().st_mtime)
                
                record = {
                    "expiry": expiry_date,
                    "Timestamp": timestamp,
                    "Spot": spot,
                    "PCR Ranged (1%)": pcr_bands.get("PCR Ranged (1%)", 0),
                    "PCR Ranged (2%)": pcr_bands.get("PCR Ranged (2%)", 0),
                    "PCR Ranged (3%)": pcr_bands.get("PCR Ranged (3%)", 0),
                    "PCR Ranged (4%)": pcr_bands.get("PCR Ranged (4%)", 0),
                    "PCR Ranged (5%)": pcr_bands.get("PCR Ranged (5%)", 0),
                    "PCR Overall": pcr_overall,
                    "Major Support": sr_res["max_support"].strike,
                    "Major Resistance": sr_res["max_resistance"].strike,
                    "Immediate Support": sr_res["top_support"][0].strike if sr_res["top_support"] else 0,
                    "Immediate Resistance": sr_res["top_resistance"][0].strike if sr_res["top_resistance"] else 0
                }
                
                # 4. Save to MySQL
                db.save_analysis_record(record)
                
                # 5. Save to MongoDB (Raw Metadata)
                raw_meta = {
                    "source_file": str(file_path),
                    "captured_at": timestamp.isoformat(),
                    "type": "historic_import",
                    "inferred_market_date": date_str,
                    "inferred_expiry": expiry_date
                }
                db.save_raw_snapshot(raw_meta, expiry_date, timestamp.isoformat())
                processed_count += 1
                
            except Exception as e:
                logger.error(f"Error processing {file_path}: {e}")
                error_count += 1

    db.close()
    logger.info(f"Bulk Sync Complete. Processed: {processed_count}, Errors: {error_count}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="OptEazy Database Sync Utility")
    parser.add_argument("--reset", action="store_true", help="Wipe databases before syncing")
    args = parser.parse_args()
    
    sync_all_files(reset=args.reset)
