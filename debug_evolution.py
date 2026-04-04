import sys
import pandas as pd
from pathlib import Path
import os
import re
from datetime import datetime

# Import managers
sys.path.append(os.getcwd())
from data_manager import load_option_chain
from analysis import compute_evolution_data

input_dir = Path("c:/Users/ravur/OneDrive/Documents/opteazy/input_file/07-Apr-2026/2026-04-01")
if not input_dir.exists():
    print(f"Directory {input_dir} DOES NOT EXIST")
    sys.exit(1)

fpaths = sorted(list(input_dir.glob("*.csv")), key=lambda p: p.stat().st_mtime)

print(f"Found {len(fpaths)} files")

for f in fpaths:
    try:
        df, strike_col, ce_oi_col, pe_oi_col = load_option_chain(str(f))
        print(f"File {f.name}: {len(df)} rows, strike: {strike_col}, ce: {ce_oi_col}, pe: {pe_oi_col}")
    except Exception as e:
        print(f"File {f.name}: FAILED load_option_chain - {e}")

try:
    # Explicitly call compute_evolution_data with loggers or modified local version to see errors
    evolution_df = compute_evolution_data([str(p) for p in fpaths], load_option_chain)
    print(f"Evolution DF: {len(evolution_df)} rows")
    if not evolution_df.empty:
        print(evolution_df.head())
    else:
        print("Evolution DF is EMPTY")
except Exception as e:
    print(f"compute_evolution_data CRASHED: {e}")
    import traceback
    traceback.print_exc()
