import os
import sys
import argparse
from db_connector import OptEazyDB

def main():
    """Diagnostic tool to verify MySQL and MongoDB connectivity."""
    print("----------------------------------------------------")
    print("OptEazy Database Diagnostic Tool")
    print("----------------------------------------------------")

    # Allow custom connection parameters for testing
    parser = argparse.ArgumentParser(description="Test connections to MySQL/MongoDB.")
    parser.add_argument("--mysql-host", default=os.getenv("MYSQL_HOST", "localhost"))
    parser.add_argument("--mongo-uri", default=os.getenv("MONGO_URI", "mongodb://localhost:27017/"))
    args = parser.parse_args()

    # Update environment for runtime override
    os.environ["MYSQL_HOST"] = args.mysql_host
    os.environ["MONGO_URI"] = args.mongo_uri

    db = OptEazyDB()
    
    print(f"\n[SCAN] Testing MySQL connection (Host: {args.mysql_host})...")
    if db.connect_mysql():
        print("SUCCESS: MySQL is reachable and authenticated!")
    else:
        print("FAILED: MySQL is unreachable. Ensure the service is running.")

    print(f"\n[SCAN] Testing MongoDB connection (URI: {args.mongo_uri})...")
    if db.connect_mongo():
        print("SUCCESS: MongoDB is reachable!")
    else:
        print("FAILED: MongoDB is unreachable. Check URI and service status.")

    print("\n----------------------------------------------------")
    print("Diagnostic Complete.")
    print("----------------------------------------------------")

if __name__ == "__main__":
    main()
