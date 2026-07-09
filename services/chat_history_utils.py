from __future__ import annotations

from typing import Any, Dict, List

from database import get_connection


CHAT_HISTORY_LIMIT = 20


def get_chat_history_for_user(user_id: int, limit: int = CHAT_HISTORY_LIMIT) -> List[Dict[str, Any]]:
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT role, content, timestamp
        FROM chat_history
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT ?
        """,
        (user_id, int(limit)),
    )
    rows = cur.fetchall() or []
    conn.close()

    # Reverse so it's chronological
    rows = list(rows)
    rows.reverse()

    return [
        {
            "role": r["role"],
            "content": r["content"],
            "timestamp": r["timestamp"],
        }
        for r in rows
    ]


def add_chat_message(user_id: int, role: str, content: str, timestamp: str | None = None) -> None:
    conn = get_connection()
    cur = conn.cursor()

    if timestamp is None:
        cur.execute(
            """
            INSERT INTO chat_history (user_id, role, content)
            VALUES (?, ?, ?)
            """,
            (user_id, role, content),
        )
    else:
        cur.execute(
            """
            INSERT INTO chat_history (user_id, role, content, timestamp)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, role, content, timestamp),
        )

    conn.commit()
    conn.close()


def clear_chat_history_for_user(user_id: int) -> None:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM chat_history WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

