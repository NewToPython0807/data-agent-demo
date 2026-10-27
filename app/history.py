"""查询历史存储（T09）。

- 建 history 表，记录：问题 / 生成的 SQL / 查询结果(JSON) / 行数 / 时间。
- 提供新增、列表、详情、清空（决策 D9：全部保留、可手动清空）。
"""
from __future__ import annotations

import json
from contextlib import closing
from datetime import datetime
from typing import Any

from app.db import DatabaseError, connect, execute_query, execute_statement

_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question TEXT NOT NULL,
    sql TEXT NOT NULL,
    result_json TEXT,
    row_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
)
"""


def _ensure_plan_column() -> None:
    """幂等为 history 补 plan 列（V3：查询计划 JSON）。"""
    existing = {row[1] for row in execute_query('PRAGMA table_info("history")')["rows"]}
    if "plan" not in existing:
        execute_statement('ALTER TABLE "history" ADD COLUMN plan TEXT NOT NULL DEFAULT ""')


def init_history_table() -> None:
    """确保 history 表存在（幂等）。"""
    execute_statement(_TABLE_SQL)
    _ensure_plan_column()


def add_history(
    question: str, sql: str, result: dict | None, plan: dict | None = None
) -> int:
    """新增一条历史记录，返回自增 id。

    result 为查询结果结构 {"columns": [...], "rows": [[...]], "row_count": N}，可空。
    plan 为查询计划（V3），可空。
    """
    result_json = json.dumps(result, ensure_ascii=False, default=str) if result else None
    plan_json = json.dumps(plan, ensure_ascii=False, default=str) if plan else ""
    row_count = int(result.get("row_count", 0)) if isinstance(result, dict) else 0
    created_at = datetime.now().isoformat(timespec="seconds")

    # INSERT 与 lastrowid 必须在同一连接上取，故直接用 connect()
    with closing(connect()) as conn:
        with conn:
            cursor = conn.execute(
                "INSERT INTO history (question, sql, result_json, row_count, plan, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (question, sql, result_json, row_count, plan_json, created_at),
            )
            return int(cursor.lastrowid)


def list_history(limit: int = 50, offset: int = 0) -> list[dict]:
    """按时间倒序返回历史列表（不含完整结果，仅行数）。"""
    limit = max(1, min(int(limit), 200))
    offset = max(0, int(offset))
    row = execute_query(
        "SELECT id, question, sql, row_count, created_at FROM history "
        "ORDER BY id DESC LIMIT ? OFFSET ?",
        (limit, offset),
    )
    return [
        {
            "id": r[0],
            "question": r[1],
            "sql": r[2],
            "row_count": r[3],
            "created_at": r[4],
        }
        for r in row["rows"]
    ]


def get_history(history_id: int) -> dict | None:
    """返回单条历史详情（含解析后的结果）。"""
    row = execute_query(
        "SELECT id, question, sql, result_json, row_count, created_at, plan "
        "FROM history WHERE id = ?",
        (history_id,),
    )
    if not row["rows"]:
        return None
    r = row["rows"][0]
    result = None
    if r[3]:
        try:
            result = json.loads(r[3])
        except json.JSONDecodeError:
            result = None
    plan = None
    if r[6]:
        try:
            plan = json.loads(r[6])
        except json.JSONDecodeError:
            plan = None
    return {
        "id": r[0],
        "question": r[1],
        "sql": r[2],
        "result": result,
        "row_count": r[4],
        "created_at": r[5],
        "plan": plan,
    }


def clear_history() -> None:
    """清空全部历史记录。"""
    execute_statement("DELETE FROM history")
