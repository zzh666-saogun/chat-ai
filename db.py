import sqlite3

DB_PATH = "chat.db"


def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    try:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_messages_session "
            "ON messages(session_id, id)"
        )
        conn.commit()
    finally:
        conn.close()


def add_message(session_id: str, role: str, content: str):
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)",
            (session_id, role, content),
        )
        conn.commit()
    finally:
        conn.close()


def get_messages(session_id: str, limit: int = 10):
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT role, content FROM messages "
            "WHERE session_id = ? ORDER BY id DESC LIMIT ?",
            (session_id, limit),
        ).fetchall()
    finally:
        conn.close()

    return [
        {"role": row["role"], "content": row["content"]}
        for row in reversed(rows)
    ]