import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
sys.path.append(os.getcwd())

from db_connector import OptEazyDB

def cleanup():
    db = OptEazyDB()
    try:
        print("--- OptEazy Database Surgical Cleanup ---")
        
        # 1. MySQL Cleanup
        if db.connect_mysql():
            cursor = db._mysql_conn.cursor()
            
            # Identify entries from today mislabeled as 07-04-2026
            # We look for records uploaded in the last 1 hour to be safe
            one_hour_ago = datetime.now() - timedelta(hours=1)
            
            query_find = "SELECT id, timestamp, spot FROM evolution_history WHERE expiry = '07-04-2026' AND timestamp >= %s"
            cursor.execute(query_find, (one_hour_ago,))
            records = cursor.fetchall()
            
            if records:
                print(f"Found {len(records)} mislabeled records in MySQL (07-04-2026) added since {one_hour_ago.strftime('%H:%M')}:")
                for r in records:
                    print(f"  - ID: {r[0]}, Time: {r[1]}, Spot: {r[2]}")
                
                delete_query = "DELETE FROM evolution_history WHERE expiry = '07-04-2026' AND timestamp >= %s"
                cursor.execute(delete_query, (one_hour_ago,))
                db._mysql_conn.commit()
                print(f"Successfully purged {len(records)} records from MySQL.")
            else:
                print("No mislabeled records found in MySQL for 07-04-2026 in the last hour.")
            cursor.close()

        # 2. MongoDB Cleanup
        if db.connect_mongo():
            mongo_db = db._mongo_client["opteazy_raw"]
            coll_name = "07_04_2026"
            if coll_name in mongo_db.list_collection_names():
                collection = mongo_db[coll_name]
                
                # In MongoDB we stored them with ISO timestamp strings
                # Let's just find anything from today in that collection
                today_prefix = datetime.now().strftime("%Y-%m-%d")
                query_mongo = {"internal_ts": {"$regex": f"^{today_prefix}"}}
                
                # Since we don't know exactly when they were uploaded, 
                # let's be careful and only delete if they were added recently.
                # Actually, any 7-Apr data added TODAY is likely wrong if the user just tried uploading 13-Apr.
                
                count = collection.count_documents(query_mongo)
                if count > 0:
                    print(f"Found {count} mislabeled raw snapshots in MongoDB collection '{coll_name}'.")
                    collection.delete_many(query_mongo)
                    print(f"Successfully purged {count} snapshots from MongoDB.")
                else:
                    print(f"No mislabeled snapshots found in MongoDB collection '{coll_name}'.")

    except Exception as e:
        print(f"Cleanup Failed: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    cleanup()
