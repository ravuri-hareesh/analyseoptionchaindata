import os
import shutil
from pathlib import Path
from db_connector import OptEazyDB

def nuclear_reset():
    root = Path.cwd()
    print("🚀 INITIALIZING NUCLEAR RESET...")

    # --- 1. PURGE FILE SYSTEM ---
    dirs_to_clear = ["input_file", "output", "file_inputs"]
    for d_name in dirs_to_clear:
        d_path = root / d_name
        if d_path.exists():
            print(f"📁 Clearing {d_name} directory...")
            for item in d_path.iterdir():
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()
            # Ensure .gitkeep stays if it existed, or just keep folder empty
            (d_path / ".gitkeep").touch()

    # --- 2. PURGE DATABASES ---
    db = OptEazyDB()
    
    # MySQL Truncate
    if db.connect_mysql():
        print("🗄️ Purging MySQL analysis records...")
        try:
            cursor = db._mysql_conn.cursor()
            cursor.execute("DELETE FROM evolution_history") 
            db._mysql_conn.commit()
            cursor.close()
            print("  ✅ MySQL transition successful.")
        except Exception as e:
            print(f"  ❌ MySQL error: {e}")
    
    # MongoDB Drop
    if db.connect_mongo():
        print("💾 Dropping MongoDB raw snapshots...")
        try:
            db._mongo_client.drop_database("opteazy_raw")
            print("  ✅ MongoDB transition successful.")
        except Exception as e:
            print(f"  ❌ MongoDB error: {e}")
    
    db.close()

    print("\n" + "="*40)
    print("✨ SURGICAL RESET COMPLETE")
    print("Your environment is now a clean slate.")
    print("="*40)
    print("\n👉 Next Step: Upload 2 fresh files to verify the Multi-file system.")

if __name__ == "__main__":
    nuclear_reset()
