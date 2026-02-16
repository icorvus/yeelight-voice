import json
import sqlite3
from pathlib import Path

_DB_PATH = Path(__file__).resolve().parent.parent.parent / "data.db"


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init():
    with _conn() as conn:
        conn.executescript("""
            DROP TABLE IF EXISTS messages;
            CREATE TABLE IF NOT EXISTS message_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                messages_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS bulbs (
                bulb_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                ip TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)


def save_messages_json(messages_json: bytes):
    with _conn() as conn:
        conn.execute(
            "INSERT INTO message_runs (messages_json) VALUES (?)",
            (messages_json.decode(),),
        )


def load_all_messages_json() -> bytes | None:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT messages_json FROM message_runs ORDER BY id"
        ).fetchall()
    if not rows:
        return None
    merged: list = []
    for row in rows:
        merged.extend(json.loads(row["messages_json"]))
    return json.dumps(merged).encode()


def clear_messages():
    with _conn() as conn:
        conn.execute("DELETE FROM message_runs")


def save_bulbs(bulbs_dict: dict[str, object]):
    with _conn() as conn:
        for bulb_id, info in bulbs_dict.items():
            conn.execute(
                """INSERT INTO bulbs (bulb_id, name, ip, updated_at)
                   VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                   ON CONFLICT(bulb_id) DO UPDATE SET
                       name=excluded.name, ip=excluded.ip,
                       updated_at=excluded.updated_at""",
                (bulb_id, info.name, info.ip),
            )


def load_bulbs() -> list[dict]:
    with _conn() as conn:
        rows = conn.execute("SELECT bulb_id, name, ip FROM bulbs").fetchall()
    return [
        {"bulb_id": row["bulb_id"], "name": row["name"], "ip": row["ip"]}
        for row in rows
    ]


def clear_bulbs():
    with _conn() as conn:
        conn.execute("DELETE FROM bulbs")
