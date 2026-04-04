import sys
import pandas as pd
from pathlib import Path
import os
import re
from datetime import datetime

# Import managers
sys.path.append(os.getcwd())
from data_manager import load_option_chain
from analysis import (compute_support_resistance, compute_pcr, Level)

input_dir = Path("c:/Users/ravur/OneDrive/Documents/opteazy/input_file/07-Apr-2026/2026-04-01")
if not input_dir.exists():
    print(f"Directory {input_dir} DOES NOT EXIST")
    sys.exit(1)

fpaths = sorted(list(input_dir.glob("*.csv")), key=lambda p: p.stat().st_mtime)

print(f"Found {len(fpaths)} files")

records = []
for fpath in fpaths:
    print(f"\nProcessing {fpath.name}...")
    try:
        df, strike_col, ce_oi_col, pe_oi_col = load_option_chain(str(fpath))
        print(f"  Loaded {len(df)} rows. Strike: {strike_col}, CE: {ce_oi_col}, PE: {pe_oi_col}")
        
        # 1. Basic Support/Resistance/Smoothed Data
        res = compute_support_resistance(df, strike_col, ce_oi_col, pe_oi_col, top_n=5, smooth_window=3)
        data = res["data"]
        print(f"  Support/Resistance computed. Data len: {len(data)}")
        
        # 2. PCR
        pcr_res = compute_pcr(df, strike_col, ce_oi_col, pe_oi_col)
        pcr_overall = pcr_res["overall_pcr"]
        print(f"  PCR Result: {pcr_overall}")
        
        # 3. Precision Spot Detection
        spot = 0
        if "Spot Price" in df.columns and df["Spot Price"].iloc[0] > 0:
            spot = float(df["Spot Price"].iloc[0])
            print(f"  Spot found in 'Spot Price': {spot}")
        elif "Underlying Value" in df.columns and df["Underlying Value"].iloc[0] > 0:
             spot = float(df["Underlying Value"].iloc[0])
             print(f"  Spot found in 'Underlying Value': {spot}")
        
        # --- SYNTHETIC SPOT RECONSTRUCTION (Layer 2) ---
        if spot == 0:
             try:
                 cols = list(df.columns)
                 ltp_indices = [i for i, c in enumerate(cols) if "LTP" in str(c).upper() or "LAST" in str(c).upper()]
                 if len(ltp_indices) >= 2:
                     ce_ltp_col = cols[ltp_indices[0]] 
                     pe_ltp_col = cols[ltp_indices[-1]] 
                     temp = df[[strike_col, ce_ltp_col, pe_ltp_col]].copy()
                     from utils import to_numeric
                     temp[strike_col] = to_numeric(temp[strike_col])
                     temp[ce_ltp_col] = to_numeric(temp[ce_ltp_col])
                     temp[pe_ltp_col] = to_numeric(temp[pe_ltp_col])
                     temp = temp.dropna()
                     if not temp.empty:
                         temp["cp_diff"] = (temp[ce_ltp_col] - temp[pe_ltp_col]).abs()
                         atm_row = temp.nsmallest(1, "cp_diff").iloc[0]
                         if atm_row[ce_ltp_col] > 0 or atm_row[pe_ltp_col] > 0:
                             spot = float(atm_row[strike_col] + (atm_row[ce_ltp_col] - atm_row[pe_ltp_col]))
                             print(f"  Synthetic Spot Decoded: {spot}")
             except: pass

        if spot == 0:
            print("  Spot is 0, calculating ATM fallback...")
            data["oi_sum"] = data["ce_oi_s"] + data["pe_oi_s"]
            data["oi_diff_ratio"] = (data["ce_oi_s"] - data["pe_oi_s"]).abs() / (data["oi_sum"] + 1)
            spot_row = data.nsmallest(1, "oi_diff_ratio").iloc[0]
            spot = float(spot_row["strike"])
            print(f"  Fallback Spot (ATM): {spot}")
        
        # 2. PCR Multi-Band Calculations (1% to 5%) - Updated to ATM-Centered
        pcr_bands = {}
        # Auto-detect strike interval
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
        print("  PCR bands computed.")
        
        # 4. Wall Strength Extraction
        max_s = res["max_support"].strike
        max_s_oi = res["max_support"].pe_oi
        max_r = res["max_resistance"].strike
        max_r_oi = res["max_resistance"].ce_oi
        
        # 5. Immediate Levels
        imm_s_df = data[data["strike"] < spot].nlargest(1, "pe_oi_s")
        imm_r_df = data[data["strike"] > spot].nlargest(1, "ce_oi_s")
        
        imm_s = float(imm_s_df.iloc[0]["strike"]) if not imm_s_df.empty else max_s
        imm_s_oi = float(imm_s_df.iloc[0]["pe_oi_s"]) if not imm_s_df.empty else max_s_oi
        imm_r = float(imm_r_df.iloc[0]["strike"]) if not imm_r_df.empty else max_r
        imm_r_oi = float(imm_r_df.iloc[0]["ce_oi_s"]) if not imm_r_df.empty else max_r_oi
        
        print(f"  Walls: S={max_s}, R={max_r}")
        
        # 6. Timestamp logic (skipped for brevity here, just use stem)
        ts_label = fpath.stem
        
        record_data = {
            "Timestamp": ts_label,
            "Spot": spot,
            "Major Support": max_s,
            "Major Support OI": max_s_oi,
            "Major Resistance": max_r,
            "Major Resistance OI": max_r_oi,
            "Immediate Support": imm_s,
            "Immediate Support OI": imm_s_oi,
            "Immediate Resistance": imm_r,
            "Immediate Resistance OI": imm_r_oi,
            "PCR Overall": pcr_overall
        }
        record_data.update(pcr_bands)
        records.append(record_data)
        print("  SUCCESSfully added record.")
        
    except Exception as e:
        print(f"  CRASHED: {e}")
        import traceback
        traceback.print_exc()

print(f"\nFinal Records Count: {len(records)}")
