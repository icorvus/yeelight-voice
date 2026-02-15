import sqlite3
from pathlib import Path

_DB_PATH = Path(__file__).parent / "data.db"


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init():
    with _conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL,
                content TEXT,
                tool_call_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS bulbs (
                bulb_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                ip TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)


def save_message(role: str, content: str, tool_call_id: str | None = None):
    with _conn() as conn:
        conn.execute(
            "INSERT INTO messages (role, content, tool_call_id) VALUES (?, ?, ?)",
            (role, content, tool_call_id),
        )


def load_messages() -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT role, content, tool_call_id FROM messages ORDER BY id"
        ).fetchall()
    messages = []
    for row in rows:
        msg: dict = {"role": row["role"], "content": row["content"] or ""}
        if row["tool_call_id"]:
            msg["tool_call_id"] = row["tool_call_id"]
        messages.append(msg)
    return messages


def clear_messages():
    with _conn() as conn:
        conn.execute("DELETE FROM messages")


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
