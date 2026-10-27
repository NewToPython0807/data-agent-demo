"""Golden SQL 示例库（V3-T17）。

维护“问题 → 正确 SQL”示例，问数时按相似度挑选 few-shot 注入提示词。
"""
from __future__ import annotations

from contextlib import closing
from datetime import datetime
from difflib import SequenceMatcher

from app.db import connect, execute_query, execute_statement

_GOLDEN_SQL = """
CREATE TABLE IF NOT EXISTS golden_sql (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question TEXT NOT NULL,
    sql TEXT NOT NULL,
    tags TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
)
"""

_COLUMNS = "id, question, sql, tags, created_at"


def init_golden_table() -> None:
    """幂等创建 golden_sql 表。"""
    execute_statement(_GOLDEN_SQL)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _row(r) -> dict:
    return {
        "id": r[0],
        "question": r[1],
        "sql": r[2],
        "tags": r[3],
        "created_at": r[4],
    }


def list_golden() -> list[dict]:
    rows = execute_query(f"SELECT {_COLUMNS} FROM golden_sql ORDER BY id DESC")["rows"]
    return [_row(r) for r in rows]


def create_golden(question: str, sql: str, tags: str = "") -> dict:
    now = _now()
    with closing(connect()) as conn:
        with conn:
            cursor = conn.execute(
                "INSERT INTO golden_sql (question, sql, tags, created_at) VALUES (?, ?, ?, ?)",
                (question, sql, tags, now),
            )
            new_id = int(cursor.lastrowid)
    rows = execute_query(f"SELECT {_COLUMNS} FROM golden_sql WHERE id = ?", (new_id,))["rows"]
    return _row(rows[0])


def delete_golden(golden_id: int) -> bool:
    return (
        execute_statement("DELETE FROM golden_sql WHERE id = ?", (golden_id,))["row_count"] > 0
    )


def match_golden(question: str, limit: int = 3) -> list[dict]:
    """按问题相似度挑选示例（关键词/相似度，V3 先不做向量检索）。"""
    q = (question or "").strip()
    if not q:
        return []
    scored = []
    for g in list_golden():
        ratio = SequenceMatcher(None, q, g["question"]).ratio()
        for tag in str(g.get("tags") or "").split(","):
            tag = tag.strip()
            if tag and tag in q:
                ratio += 0.1
        if ratio >= 0.3:
            scored.append((ratio, g))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [g for _, g in scored[: max(1, limit)]]
