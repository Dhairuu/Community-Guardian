import sqlite3
import os
import json
from contextlib import contextmanager

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "community_guardian.db")


def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                url TEXT,
                published_at TEXT,
                city TEXT NOT NULL,
                signal TEXT NOT NULL,
                category TEXT NOT NULL,
                severity TEXT NOT NULL,
                confidence REAL,
                similar_pattern TEXT,
                checklist TEXT,
                simple_checklist TEXT,
                helpline TEXT,
                status TEXT DEFAULT 'active',
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS daily_tips (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                city TEXT NOT NULL,
                tip TEXT NOT NULL,
                date TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.commit()


@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def save_report(report_dict: dict) -> int:
    with get_db() as conn:
        existing = conn.execute(
            "SELECT id FROM reports WHERE title = ? AND city = ? LIMIT 1",
            (report_dict["title"], report_dict["city"]),
        ).fetchone()
        if existing:
            return existing["id"]

        cursor = conn.execute(
            """INSERT INTO reports
               (source, title, content, url, published_at, city, signal, category,
                severity, confidence, similar_pattern, checklist, simple_checklist, helpline)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                report_dict["source"],
                report_dict["title"],
                report_dict["content"],
                report_dict.get("url"),
                report_dict.get("published_at"),
                report_dict["city"],
                report_dict["signal"],
                report_dict["category"],
                report_dict["severity"],
                report_dict.get("confidence"),
                report_dict.get("similar_pattern"),
                report_dict.get("checklist"),
                report_dict.get("simple_checklist"),
                report_dict.get("helpline"),
            ),
        )
        conn.commit()
        return cursor.lastrowid


def get_reports(city=None, category=None, severity=None, signal=None) -> list[dict]:
    conditions = ["status = 'active'"]  # Only show active reports
    params = []
    if city:
        conditions.append("city = ?")
        params.append(city)
    if category:
        conditions.append("category = ?")
        params.append(category)
    if severity:
        conditions.append("severity = ?")
        params.append(severity)
    if signal:
        conditions.append("signal = ?")
        params.append(signal)

    where = f"WHERE {' AND '.join(conditions)}"
    query = f"SELECT * FROM reports {where} ORDER BY created_at DESC LIMIT 50"

    with get_db() as conn:
        rows = conn.execute(query, params).fetchall()
        results = []
        for row in rows:
            d = dict(row)
            if d.get("checklist"):
                try:
                    d["checklist"] = json.loads(d["checklist"])
                except (json.JSONDecodeError, TypeError):
                    d["checklist"] = [d["checklist"]]
            results.append(d)
        return results


def update_report_status(report_id: int, status: str) -> bool:
    with get_db() as conn:
        cursor = conn.execute(
            "UPDATE reports SET status = ? WHERE id = ?", (status, report_id)
        )
        conn.commit()
        return cursor.rowcount > 0


def save_daily_tip(city: str, tip: str, date: str):
    with get_db() as conn:
        conn.execute(
            "INSERT INTO daily_tips (city, tip, date) VALUES (?, ?, ?)",
            (city, tip, date),
        )
        conn.commit()


def get_daily_tip(city: str, date: str) -> str | None:
    with get_db() as conn:
        row = conn.execute(
            "SELECT tip FROM daily_tips WHERE city = ? AND date = ? ORDER BY id DESC LIMIT 1",
            (city, date),
        ).fetchone()
        return row["tip"] if row else None
