import os
import sys
import logging
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd

# Add project root to path
sys.path.append(os.getcwd())

from data_manager import normalize_date_str, load_option_chain, get_validated_spot, save_uploaded_file, INPUT_ROOT
from db_connector import OptEazyDB

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Migrate_Metadata")
# Silencing noisy logs during migration
logging.getLogger("Data_Manager").setLevel(logging.WARNING)
logging.getLogger("DB_Connector").setLevel(logging.WARNING)

def run_surgical_migration():
    """
    Surgical Migration Rules:
    1. Rule A (Modified in Last 1 Hour): Call Live API for perfect spot synchronization (Today's Hack).
    2. Rule B (Older than 1 Hour): Use File Regex Only to generate .meta.json.
    3. Resilience: Skip 0-byte, HTML, or corrupted CSVs gracefully.
    """
    db = OptEazyDB()
    try:
        print("\n" + "="*60)
        print("   OPTEAZY SURGICAL MIGRATION & SPOT SYNCHRONIZATION")
        print("="*60 + "\n")
        
        now = datetime.now()
        one_hour_ago = now - timedelta(hours=1)
        
        stats = {"total": 0, "success": 0, "skipped": 0, "failed": 0}
        
        # Scan all directories in input_file
        all_dates = sorted([d for d in INPUT_ROOT.iterdir() if d.is_dir()])
        
        for date_dir in all_dates:
            date_str = date_dir.name
            expiries = sorted([e for e in date_dir.iterdir() if e.is_dir()])
            
            for exp_dir in expiries:
                expiry_str = exp_dir.name
                files = list(exp_dir.glob("*.csv")) + list(exp_dir.glob("*.xlsx"))
                
                if not files: continue
                
                print(f"📂 {date_str} -> {expiry_str}")
                
                for f_path in files:
                    if f_path.suffix == ".json": continue
                    stats["total"] += 1
                    
                    mtime = datetime.fromtimestamp(f_path.stat().st_mtime)
                    allow_api = mtime >= one_hour_ago
                    
                    rule_label = "[Rule A: API]" if allow_api else "[Rule B: Regex]"
                    
                    try:
                        # 1. Size check
                        if f_path.stat().st_size == 0:
                            print(f"  ⚠️ Skip (0 bytes): {f_path.name}")
                            stats["skipped"] += 1
                            continue

                        # 2. Load and Validate
                        # This might throw ValueError if corrupted/empty columns
                        df, _, _, _ = load_option_chain(f_path)
                        
                        # Trigger full re-sync (Sidecar + DBs)
                        # save_uploaded_file now re-raises errors and returns spot
                        class MockUpload:
                            def __init__(self, path):
                                self.name = path.name
                                self.path = path
                                # CRITICAL: Read before any write operations start
                                with open(path, "rb") as bf:
                                    self.buffer = bf.read()
                            def getbuffer(self):
                                return self.buffer
                        
                        spot = save_uploaded_file(MockUpload(f_path), date_str=date_str)
                        
                        print(f"  ✅ {rule_label} {f_path.name:40} | Spot: {spot:8}")
                        stats["success"] += 1
                        
                    except ValueError as e:
                        print(f"  ⏩ Skip (Corrupt): {f_path.name:40} | Reason: {str(e)[:50]}...")
                        stats["skipped"] += 1
                    except Exception as e:
                        print(f"  ❌ FAILED: {f_path.name:40} | Error: {e}")
                        stats["failed"] += 1

    except Exception as e:
        logger.error(f"Migration aborted: {e}")
    finally:
        db.close()
        print("\n" + "="*60)
        print("   MIGRATION SUMMARY")
        print(f"   Total: {stats['total']} | Success: {stats['success']} | Skipped: {stats['skipped']} | Failed: {stats['failed']}")
        print("="*60 + "\n")

if __name__ == "__main__":
    run_surgical_migration()
