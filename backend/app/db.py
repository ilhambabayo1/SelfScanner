# ============================================================
# SELF SCANNER - db.py (SQLite persistence layer)
# Device sessions (no accounts), scan log, reading history,
# metadata cache. Postgres-ready schema shape.
# ============================================================
import os
import sqlite3

from .config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS device_sessions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  device_id TEXT UNIQUE NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  scans_today INTEGER DEFAULT 0,
  scan_day TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS scanned_books (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  device_id TEXT NOT NULL,
  title TEXT,
  author TEXT,
  isbn TEXT,
  match_idx INTEGER,
  similarity REAL,
  source TEXT DEFAULT 'gemini',
  confidence REAL,
  scan_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  metadata TEXT
);
CREATE TABLE IF NOT EXISTS reading_history (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  device_id TEXT NOT NULL,
  book_key TEXT NOT NULL,
  status TEXT DEFAULT 'want-to-read',
  rating INTEGER,
  date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(device_id, book_key)
);
CREATE TABLE IF NOT EXISTS metadata_cache (
  key TEXT PRIMARY KEY,
  payload TEXT,
  fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


_initialized = False


def connect():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    global _initialized
    if not _initialized:  # lazy schema init; idempotent (IF NOT EXISTS)
        conn.executescript(SCHEMA)
        _initialized = True
    return conn


def init_db():
    with connect() as conn:
        conn.executescript(SCHEMA)


def ensure_device(device_id: str) -> None:
    if not device_id or len(device_id) > 255:
        device_id = "anon"
    with connect() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO device_sessions(device_id) VALUES (?)",
            (device_id,),
        )
        conn.execute(
            "UPDATE device_sessions SET last_active = CURRENT_TIMESTAMP "
            "WHERE device_id = ?",
            (device_id,),
        )


def check_rate_limit(device_id: str, daily_limit: int) -> bool:
    """Return True if the device is allowed to scan right now."""
    import time

    today = time.strftime("%Y-%m-%d")
    with connect() as conn:
        row = conn.execute(
            "SELECT scans_today, scan_day FROM device_sessions WHERE device_id = ?",
            (device_id,),
        ).fetchone()
        if row is None:
            return True
        used = row["scans_today"] if row["scan_day"] == today else 0
        return used < daily_limit


def record_scan(device_id: str, daily_limit: int, **book) -> None:
    import time
    import json as _json

    today = time.strftime("%Y-%m-%d")
    with connect() as conn:
        conn.execute(
            "INSERT INTO scanned_books(device_id, title, author, isbn, match_idx, "
            "similarity, source, confidence, metadata) VALUES (?,?,?,?,?,?,?,?,?)",
            (
                device_id,
                book.get("title"),
                book.get("author"),
                book.get("isbn"),
                book.get("match_idx"),
                book.get("similarity"),
                book.get("source", "gemini"),
                book.get("confidence"),
                _json.dumps(book.get("metadata") or {}),
            ),
        )
        conn.execute(
            "UPDATE device_sessions SET scans_today = "
            "CASE WHEN scan_day = ? THEN scans_today + 1 ELSE 1 END, "
            "scan_day = ? WHERE device_id = ?",
            (today, today, device_id),
        )


def shelf_add(device_id: str, book_key: str, status: str, rating=None) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO reading_history(device_id, book_key, status, rating) "
            "VALUES (?,?,?,?) "
            "ON CONFLICT(device_id, book_key) "
            "DO UPDATE SET status = excluded.status, rating = excluded.rating",
            (device_id, book_key, status, rating),
        )


def shelf_list(device_id: str):
    with connect() as conn:
        rows = conn.execute(
            "SELECT book_key, status, rating, date_added FROM reading_history "
            "WHERE device_id = ? ORDER BY date_added DESC",
            (device_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def cache_get(key: str):
    with connect() as conn:
        row = conn.execute(
            "SELECT payload FROM metadata_cache WHERE key = ?", (key,)
        ).fetchone()
    return row["payload"] if row else None


def cache_set(key: str, payload: str) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO metadata_cache(key, payload) VALUES (?,?)",
            (key, payload),
        )


def rate_book(device_id: str, book_key: str, rating: int, status: str = None) -> None:
    """Set/update a star rating; creates the shelf row if needed."""
    with connect() as conn:
        row = conn.execute(
            "SELECT id FROM reading_history WHERE device_id = ? AND book_key = ?",
            (device_id, book_key),
        ).fetchone()
        if row is None:
            conn.execute(
                "INSERT INTO reading_history(device_id, book_key, status, rating) "
                "VALUES (?,?,?,?)",
                (device_id, book_key, status or "completed", rating),
            )
        elif status:
            conn.execute(
                "UPDATE reading_history SET rating = ?, status = ? WHERE id = ?",
                (rating, status, row["id"]),
            )
        else:
            conn.execute(
                "UPDATE reading_history SET rating = ? WHERE id = ?", (rating, row["id"])
            )


def shelf_rows(device_id: str):
    with connect() as conn:
        rows = conn.execute(
            "SELECT book_key, status, rating, date_added FROM reading_history "
            "WHERE device_id = ? ORDER BY date_added DESC",
            (device_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def scan_meta(device_id: str):
    """Latest scan metadata JSON per matched book idx for a device."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT match_idx, metadata FROM scanned_books WHERE device_id = ? "
            "AND match_idx IS NOT NULL AND metadata IS NOT NULL GROUP BY match_idx",
            (device_id,),
        ).fetchall()
    return {int(r["match_idx"]): r["metadata"] for r in rows}
