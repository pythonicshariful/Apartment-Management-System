import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), 'apartments.db')

APARTMENTS = [
    ('A1', 'Available', None),
    ('A2', 'Available', None),
    ('B1', 'Available', None),
    ('B2', 'Available', None),
]

def get_db():
    """Get a database connection with row_factory."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Initialize database schema and seed apartments."""
    with get_db() as conn:
        cursor = conn.cursor()

        # Apartments table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS apartments (
                id        TEXT PRIMARY KEY,
                status    TEXT NOT NULL DEFAULT 'Available',
                booked_by TEXT DEFAULT NULL
            )
        """)

        # Customers table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS customers (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                apartment_id   TEXT NOT NULL UNIQUE,
                name           TEXT NOT NULL,
                address        TEXT NOT NULL,
                phone          TEXT NOT NULL,
                profile_pic    TEXT DEFAULT NULL,
                document_path  TEXT DEFAULT NULL,
                booked_at      TEXT NOT NULL,
                FOREIGN KEY (apartment_id) REFERENCES apartments(id)
            )
        """)

        # Audit logs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp    TEXT NOT NULL,
                action       TEXT NOT NULL,
                performed_by TEXT NOT NULL,
                details      TEXT
            )
        """)

        # Seed apartments only if table is empty
        existing = cursor.execute("SELECT COUNT(*) FROM apartments").fetchone()[0]
        if existing == 0:
            cursor.executemany(
                "INSERT INTO apartments (id, status, booked_by) VALUES (?, ?, ?)",
                APARTMENTS
            )

        conn.commit()


def log_audit(action: str, performed_by: str, details: str = ""):
    """Write an entry to the audit_logs table."""
    with get_db() as conn:
        conn.execute(
            "INSERT INTO audit_logs (timestamp, action, performed_by, details) VALUES (?, ?, ?, ?)",
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), action, performed_by, details)
        )
        conn.commit()


def get_all_apartments():
    """Return all apartments with optional customer join."""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT a.id, a.status, a.booked_by,
                   c.name, c.phone, c.address,
                   c.profile_pic, c.document_path, c.booked_at
            FROM apartments a
            LEFT JOIN customers c ON c.apartment_id = a.id
            ORDER BY a.id
        """).fetchall()
        return [dict(r) for r in rows]


def get_apartment(apt_id: str):
    """Return a single apartment with customer data."""
    with get_db() as conn:
        row = conn.execute("""
            SELECT a.id, a.status, a.booked_by,
                   c.id as customer_id, c.name, c.phone, c.address,
                   c.profile_pic, c.document_path, c.booked_at
            FROM apartments a
            LEFT JOIN customers c ON c.apartment_id = a.id
            WHERE a.id = ?
        """, (apt_id,)).fetchone()
        return dict(row) if row else None


def book_apartment(apt_id: str, company: str, name: str, address: str,
                   phone: str, profile_pic: str = None, document_path: str = None):
    """Book an apartment and create a customer record."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_db() as conn:
        conn.execute(
            "UPDATE apartments SET status='Booked', booked_by=? WHERE id=? AND status='Available'",
            (company, apt_id)
        )
        conn.execute("""
            INSERT INTO customers (apartment_id, name, address, phone, profile_pic, document_path, booked_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (apt_id, name, address, phone, profile_pic, document_path, now))
        conn.commit()


def edit_customer(apt_id: str, name: str, address: str, phone: str,
                  profile_pic: str = None, document_path: str = None):
    """Update existing customer record for an apartment."""
    with get_db() as conn:
        if profile_pic and document_path:
            conn.execute("""
                UPDATE customers SET name=?, address=?, phone=?, profile_pic=?, document_path=?
                WHERE apartment_id=?
            """, (name, address, phone, profile_pic, document_path, apt_id))
        elif profile_pic:
            conn.execute("""
                UPDATE customers SET name=?, address=?, phone=?, profile_pic=?
                WHERE apartment_id=?
            """, (name, address, phone, profile_pic, apt_id))
        elif document_path:
            conn.execute("""
                UPDATE customers SET name=?, address=?, phone=?, document_path=?
                WHERE apartment_id=?
            """, (name, address, phone, document_path, apt_id))
        else:
            conn.execute("""
                UPDATE customers SET name=?, address=?, phone=?
                WHERE apartment_id=?
            """, (name, address, phone, apt_id))
        conn.commit()


def cancel_booking(apt_id: str):
    """Cancel a booking: reset apartment and remove customer record."""
    with get_db() as conn:
        conn.execute(
            "UPDATE apartments SET status='Available', booked_by=NULL WHERE id=?",
            (apt_id,)
        )
        conn.execute("DELETE FROM customers WHERE apartment_id=?", (apt_id,))
        conn.commit()


def get_audit_logs(limit: int = 200):
    """Return recent audit log entries."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM audit_logs ORDER BY id DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
