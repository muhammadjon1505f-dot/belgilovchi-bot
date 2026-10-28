"""
Belgilovchi Bot — SQLite Ma'lumotlar Bazasi Moduli.
"""
import sqlite3
import datetime
from pathlib import Path

class Database:
    def __init__(self, db_path="belgilovchi.db"):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    first_name TEXT,
                    username TEXT,
                    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS groups (
                    chat_id INTEGER PRIMARY KEY,
                    title TEXT,
                    username TEXT,
                    members_count INTEGER DEFAULT 0,
                    is_active INTEGER DEFAULT 1,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS group_members (
                    chat_id INTEGER,
                    user_id INTEGER,
                    first_name TEXT,
                    username TEXT,
                    last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (chat_id, user_id)
                );

                CREATE TABLE IF NOT EXISTS call_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER,
                    user_id INTEGER,
                    call_type TEXT,
                    reason TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

    def add_or_update_user(self, user_id: int, first_name: str, username: str = None):
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO users (user_id, first_name, username, last_seen)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id) DO UPDATE SET
                    first_name = excluded.first_name,
                    username = excluded.username,
                    last_seen = CURRENT_TIMESTAMP
            """, (user_id, first_name, username))

    def add_or_update_group(self, chat_id: int, title: str, username: str = None, members_count: int = 0):
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO groups (chat_id, title, username, members_count, is_active)
                VALUES (?, ?, ?, ?, 1)
                ON CONFLICT(chat_id) DO UPDATE SET
                    title = excluded.title,
                    username = excluded.username,
                    members_count = excluded.members_count,
                    is_active = 1
            """, (chat_id, title, username, members_count))

    def deactivate_group(self, chat_id: int):
        with self._get_connection() as conn:
            conn.execute("UPDATE groups SET is_active = 0 WHERE chat_id = ?", (chat_id,))

    def track_member_activity(self, chat_id: int, user_id: int, first_name: str, username: str = None):
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO group_members (chat_id, user_id, first_name, username, last_active)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(chat_id, user_id) DO UPDATE SET
                    first_name = excluded.first_name,
                    username = excluded.username,
                    last_active = CURRENT_TIMESTAMP
            """, (chat_id, user_id, first_name, username))

    def get_group_members(self, chat_id: int, limit: int = 250):
        with self._get_connection() as conn:
            cur = conn.execute(
                "SELECT user_id, first_name, username FROM group_members WHERE chat_id = ? ORDER BY last_active DESC LIMIT ?",
                (chat_id, limit)
            )
            return [dict(row) for row in cur.fetchall()]

    def log_call(self, chat_id: int, user_id: int, call_type: str, reason: str = ""):
        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO call_logs (chat_id, user_id, call_type, reason) VALUES (?, ?, ?, ?)",
                (chat_id, user_id, call_type, reason)
            )

    def get_stats(self):
        with self._get_connection() as conn:
            total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            total_groups = conn.execute("SELECT COUNT(*) FROM groups WHERE is_active = 1").fetchone()[0]
            total_calls = conn.execute("SELECT COUNT(*) FROM call_logs").fetchone()[0]
            total_tracked_members = conn.execute("SELECT COUNT(*) FROM group_members").fetchone()[0]
            return {
                "total_users": total_users,
                "total_groups": total_groups,
                "total_calls": total_calls,
                "total_tracked_members": total_tracked_members,
            }
