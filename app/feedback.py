"""结果反馈（V3-T21）：赞/踩。"""
from __future__ import annotations

from contextlib import closing
from datetime import datetime

from app.db import connect, execute_query, execute_statement

_FEEDBACK_SQL = """
CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    history_id INTEGER,
    question TEXT NOT NULL DEFAULT '',
    sql TEXT NOT NULL DEFAULT '',
    rating INTEGER NOT NULL,
    comment TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
)
"""

_COLUMNS = "id, history_id, question, sql, rating, comment, created_at"


def init_feedback_table() -> None:
    """幂等创建 feedback 表。"""
    execute_statement(_FEEDBACK_SQL)


def _row(r) -> dict:
    return {
        "id": r[0],
        "history_id": r[1],
        "question": r[2],
        "sql": r[3],
        "rating": r[4],
        "comment": r[5],
        "created_at": r[6],
    }


def add_feedback(
    history_id: int | None,
    question: str,
    sql: str,
    rating: int,
    comment: str = "",
) -> dict:
    now = datetime.now().isoformat(timespec="seconds")
    with closing(connect()) as conn:
        with conn:
            cursor = conn.execute(
                "INSERT INTO feedback (history_id, question, sql, rating, comment, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (history_id, question, sql, int(rating), comment, now),
            )
            new_id = int(cursor.lastrowid)
    rows = execute_query(f"SELECT {_COLUMNS} FROM feedback WHERE id = ?", (new_id,))["rows"]
    return _row(rows[0])


def list_feedback(limit: int = 50) -> list[dict]:
    limit = max(1, min(int(limit), 200))
    rows = execute_query(
        f"SELECT {_COLUMNS} FROM feedback ORDER BY id DESC LIMIT ?", (limit,)
    )["rows"]
    return [_row(r) for r in rows]


def feedback_stats() -> dict:
    """返回查询数、赞/踩等基础统计。"""

    def count(sql: str) -> int:
        return int(execute_query(sql)["rows"][0][0])

    total = count("SELECT COUNT(*) FROM feedback")
    up = count("SELECT COUNT(*) FROM feedback WHERE rating = 1")
    down = count("SELECT COUNT(*) FROM feedback WHERE rating = -1")
    queries = count("SELECT COUNT(*) FROM history")
    return {
        "queries": queries,
        "feedback_total": total,
        "up": up,
        "down": down,
        "up_rate": round(up / total * 100, 1) if total else 0.0,
    }
