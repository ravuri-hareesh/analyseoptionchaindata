import sqlite3
import bcrypt
import os
from auth_manager import AuthManager

def init_database():
    db_path = "users.db"
    auth_manager = AuthManager(db_path)
    
    # Check if admin already exists
    with sqlite3.connect(db_path) as conn:
        cursor = conn.execute("SELECT 1 FROM users WHERE username = ?", ("admin",))
        if cursor.fetchone():
            print("Admin user already exists.")
            return

    # User's default admin: admin / Hareesh@9889
    success = auth_manager.add_user(
        username="admin",
        email="admin@opteazy.io",
        name="System Administrator (Hareesh)",
        password="Hareesh@9889",
        role="admin"
    )
    
    if success:
        print("Database initialized successfully with default admin: admin / Hareesh@9889")
    else:
        print("Failed to initialize database.")

if __name__ == "__main__":
    init_database()
