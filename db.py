import sqlite3
import json
from datetime import datetime
from config import DB_PATH


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS circles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id TEXT NOT NULL,
            admin_id TEXT NOT NULL,
            name TEXT NOT NULL,
            contribution_amount REAL NOT NULL,
            max_members INTEGER NOT NULL,
            cycle_days INTEGER NOT NULL DEFAULT 7,
            current_round INTEGER NOT NULL DEFAULT 1,
            status TEXT NOT NULL DEFAULT 'recruiting',
            payout_order TEXT DEFAULT '[]',
            created_at TEXT NOT NULL,
            next_deadline TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            circle_id INTEGER NOT NULL,
            user_id TEXT NOT NULL,
            username TEXT,
            full_name TEXT,
            wallet_address TEXT NOT NULL,
            encrypted_key TEXT NOT NULL,
            payout_position INTEGER,
            joined_at TEXT NOT NULL,
            FOREIGN KEY (circle_id) REFERENCES circles(id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS contributions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            circle_id INTEGER NOT NULL,
            member_id INTEGER NOT NULL,
            round_number INTEGER NOT NULL,
            amount REAL NOT NULL,
            tx_hash TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            contributed_at TEXT,
            FOREIGN KEY (circle_id) REFERENCES circles(id),
            FOREIGN KEY (member_id) REFERENCES members(id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS payouts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            circle_id INTEGER NOT NULL,
            round_number INTEGER NOT NULL,
            recipient_member_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            tx_hash TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            paid_at TEXT,
            FOREIGN KEY (circle_id) REFERENCES circles(id),
            FOREIGN KEY (recipient_member_id) REFERENCES members(id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS penalties (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            circle_id INTEGER NOT NULL,
            member_id INTEGER NOT NULL,
            round_number INTEGER NOT NULL,
            amount REAL NOT NULL,
            tx_hash TEXT,
            reason TEXT,
            applied_at TEXT,
            FOREIGN KEY (circle_id) REFERENCES circles(id),
            FOREIGN KEY (member_id) REFERENCES members(id)
        )
    """)

    conn.commit()
    conn.close()


# --- Circle queries ---

def create_circle(chat_id, admin_id, name, contribution_amount, max_members, cycle_days=7):
    conn = get_conn()
    c = conn.cursor()
    now = datetime.utcnow().isoformat()
    c.execute("""
        INSERT INTO circles (chat_id, admin_id, name, contribution_amount, max_members, cycle_days, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (str(chat_id), str(admin_id), name, contribution_amount, max_members, cycle_days, now))
    circle_id = c.lastrowid
    conn.commit()
    conn.close()
    return circle_id


def get_circle_by_chat(chat_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM circles WHERE chat_id = ? ORDER BY id DESC LIMIT 1", (str(chat_id),))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def get_circle_by_id(circle_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM circles WHERE id = ?", (circle_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def update_circle(circle_id, **kwargs):
    conn = get_conn()
    c = conn.cursor()
    fields = ", ".join(f"{k} = ?" for k in kwargs)
    values = list(kwargs.values()) + [circle_id]
    c.execute(f"UPDATE circles SET {fields} WHERE id = ?", values)
    conn.commit()
    conn.close()


def get_all_active_circles():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM circles WHERE status IN ('recruiting', 'active')")
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


# --- Member queries ---

def add_member(circle_id, user_id, username, full_name, wallet_address, encrypted_key):
    conn = get_conn()
    c = conn.cursor()
    now = datetime.utcnow().isoformat()
    c.execute("""
        INSERT INTO members (circle_id, user_id, username, full_name, wallet_address, encrypted_key, joined_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (circle_id, str(user_id), username, full_name, wallet_address, encrypted_key, now))
    member_id = c.lastrowid
    conn.commit()
    conn.close()
    return member_id


def get_member(circle_id, user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM members WHERE circle_id = ? AND user_id = ?", (circle_id, str(user_id)))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def get_members(circle_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM members WHERE circle_id = ?", (circle_id,))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def member_count(circle_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) as cnt FROM members WHERE circle_id = ?", (circle_id,))
    row = c.fetchone()
    conn.close()
    return row["cnt"]


def update_member(member_id, **kwargs):
    conn = get_conn()
    c = conn.cursor()
    fields = ", ".join(f"{k} = ?" for k in kwargs)
    values = list(kwargs.values()) + [member_id]
    c.execute(f"UPDATE members SET {fields} WHERE id = ?", values)
    conn.commit()
    conn.close()


# --- Contribution queries ---

def record_contribution(circle_id, member_id, round_number, amount, tx_hash=None, status="confirmed"):
    conn = get_conn()
    c = conn.cursor()
    now = datetime.utcnow().isoformat()
    c.execute("""
        INSERT INTO contributions (circle_id, member_id, round_number, amount, tx_hash, status, contributed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (circle_id, member_id, round_number, amount, tx_hash, status, now))
    conn.commit()
    conn.close()


def get_round_contributions(circle_id, round_number):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT c.*, m.user_id, m.username, m.full_name
        FROM contributions c
        JOIN members m ON c.member_id = m.id
        WHERE c.circle_id = ? AND c.round_number = ? AND c.status = 'confirmed'
    """, (circle_id, round_number))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def has_contributed(circle_id, member_id, round_number):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT id FROM contributions
        WHERE circle_id = ? AND member_id = ? AND round_number = ? AND status = 'confirmed'
    """, (circle_id, member_id, round_number))
    row = c.fetchone()
    conn.close()
    return row is not None


# --- Payout queries ---

def record_payout(circle_id, round_number, recipient_member_id, amount, tx_hash=None, status="confirmed"):
    conn = get_conn()
    c = conn.cursor()
    now = datetime.utcnow().isoformat()
    c.execute("""
        INSERT INTO payouts (circle_id, round_number, recipient_member_id, amount, tx_hash, status, paid_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (circle_id, round_number, recipient_member_id, amount, tx_hash, status, now))
    conn.commit()
    conn.close()


def get_payouts(circle_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT p.*, m.username, m.full_name
        FROM payouts p
        JOIN members m ON p.recipient_member_id = m.id
        WHERE p.circle_id = ?
        ORDER BY p.round_number
    """, (circle_id,))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


# --- Penalty queries ---

def record_penalty(circle_id, member_id, round_number, amount, tx_hash=None, reason="Late contribution"):
    conn = get_conn()
    c = conn.cursor()
    now = datetime.utcnow().isoformat()
    c.execute("""
        INSERT INTO penalties (circle_id, member_id, round_number, amount, tx_hash, reason, applied_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (circle_id, member_id, round_number, amount, tx_hash, reason, now))
    conn.commit()
    conn.close()


def get_all_circles():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM circles ORDER BY created_at DESC")
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_contributions():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM contributions ORDER BY contributed_at DESC")
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_payouts():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM payouts ORDER BY paid_at DESC")
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]
