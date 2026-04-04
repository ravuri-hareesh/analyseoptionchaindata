import os
import shutil
from pathlib import Path

def recover_and_cleanup():
    root_dir = Path.cwd()
    input_dir = root_dir / "input_file"
    
    if not input_dir.exists():
        print(f"❌ Error: {input_dir} not found. Run this from your project root.")
        return

    recovery_bank = {}
    print("📂 Phase 1: Building Recovery Bank (Scanning for duplicates)...")
    
    # Scan root and all subfolders EXCEPT input_file for valid CSVs
    for root, dirs, files in os.walk(root_dir):
        if "input_file" in root:
            continue
        
        for file in files:
            if file.endswith(".csv"):
                file_path = Path(root) / file
                if file_path.stat().st_size > 0:
                    # Store the one we found. If duplicate names exist, newest one wins
                    recovery_bank[file] = file_path

    print(f"📊 Found {len(recovery_bank)} valid CSV files for potential recovery.")

    restored_count = 0
    purged_count = 0
    meta_purged_count = 0

    print("\n🚀 Phase 2: Processing 'input_file' directory...")
    
    # Process input_file recursively
    for root, dirs, files in os.walk(input_dir):
        for file in files:
            file_path = Path(root) / file
            
            # Case 1: 0-byte CSV
            if file.endswith(".csv") and file_path.stat().st_size == 0:
                if file in recovery_bank:
                    # RECOVERY
                    source = recovery_bank[file]
                    shutil.copy2(source, file_path)
                    print(f"  ✅ Restored: {file} from {source}")
                    restored_count += 1
                else:
                    # PURGE
                    file_path.unlink()
                    print(f"  🗑️ Purged (No recovery found): {file}")
                    purged_count += 1
                    
                    # Clean up orphaned sidecar if it exists
                    meta_path = file_path.with_suffix(".csv.meta.json")
                    if meta_path.exists():
                        meta_path.unlink()
                        meta_purged_count += 1

            # Case 2: Orphaned meta.json (base file was already deleted or doesn't exist)
            elif file.endswith(".meta.json"):
                base_csv = file_path.parent / file.replace(".meta.json", "")
                if not base_csv.exists():
                    file_path.unlink()
                    meta_purged_count += 1

    print("\n" + "="*40)
    print("✨ RECOVERY & CLEANUP COMPLETE")
    print(f"✅ Files Restored: {restored_count}")
    print(f"🗑️ Files Purged:   {purged_count}")
    print(f"📄 Meta-json Cleaned: {meta_purged_count}")
    print("="*40)
    print("\n👉 Now safe to run: python migrate_metadata.py")

if __name__ == "__main__":
    recover_and_cleanup()
