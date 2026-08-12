import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), 'sessions.db')

def get_session_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_session_db():
    with get_session_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                role TEXT NOT NULL,
                user_agent TEXT,
                ip_address TEXT,
                created_at TEXT NOT NULL,
                last_active_at TEXT NOT NULL
            )
        """)
        conn.commit()

def create_session(session_id: str, role: str, user_agent: str, ip_address: str):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_session_db() as conn:
        conn.execute(
            "INSERT INTO sessions (session_id, role, user_agent, ip_address, created_at, last_active_at) VALUES (?, ?, ?, ?, ?, ?)",
            (session_id, role, user_agent, ip_address, now, now)
        )
        conn.commit()

def get_session(session_id: str):
    with get_session_db() as conn:
        row = conn.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,)).fetchone()
        return dict(row) if row else None

def get_active_sessions():
    with get_session_db() as conn:
        rows = conn.execute("SELECT * FROM sessions ORDER BY last_active_at DESC").fetchall()
        return [dict(r) for r in rows]

def delete_session(session_id: str):
    with get_session_db() as conn:
        conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
        conn.commit()

def update_session_activity(session_id: str):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_session_db() as conn:
        conn.execute("UPDATE sessions SET last_active_at = ? WHERE session_id = ?", (now, session_id))
        conn.commit()
