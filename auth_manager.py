import sqlite3
import bcrypt
from pathlib import Path
from typing import Dict, List, Optional, Any

class AuthManager:
    def __init__(self, db_path: str = "users.db"):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    username TEXT PRIMARY KEY,
                    email TEXT NOT NULL,
                    name TEXT NOT NULL,
                    password TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'public_user'
                )
            """)
            conn.commit()

    def hash_password(self, password: str) -> str:
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    def check_password(self, password: str, hashed: str) -> bool:
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

    def add_user(self, username: str, email: str, name: str, password: str, role: str = "public_user") -> bool:
        hashed_pw = self.hash_password(password)
        try:
            with self._get_connection() as conn:
                conn.execute(
                    "INSERT INTO users (username, email, name, password, role) VALUES (?, ?, ?, ?, ?)",
                    (username, email, name, hashed_pw, role)
                )
                conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def get_user_credentials(self) -> Dict[str, Any]:
        """Returns credentials in the format expected by streamlit-authenticator."""
        credentials = {"usernames": {}}
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT username, email, name, password, role FROM users")
            for row in cursor:
                username, email, name, password, role = row
                credentials["usernames"][username] = {
                    "email": email,
                    "name": name,
                    "password": password,
                    "role": role # Custom field for our app
                }
        return credentials

    def update_user_role(self, username: str, new_role: str):
        with self._get_connection() as conn:
            conn.execute("UPDATE users SET role = ? WHERE username = ?", (new_role, username))
            conn.commit()

    def get_user_role(self, username: str) -> Optional[str]:
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT role FROM users WHERE username = ?", (username,))
            row = cursor.fetchone()
            return row[0] if row else None

    def delete_user(self, username: str):
        with self._get_connection() as conn:
            conn.execute("DELETE FROM users WHERE username = ?", (username,))
            conn.commit()
            
    def get_all_users(self) -> List[Dict[str, Any]]:
        users = []
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT username, email, name, role FROM users")
            for row in cursor:
                users.append({
                    "username": row[0],
                    "email": row[1],
                    "name": row[2],
                    "role": row[3]
                })
        return users
