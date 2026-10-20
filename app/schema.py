"""表结构读取（T06）。

读取数据库中的表名与字段信息，供前端展示（FR-11）与 LLM 提示组装（T14）使用。
"""
from __future__ import annotations

import sqlite3
from contextlib import closing

from app.db import DatabaseError, connect


def list_tables() -> list[str]:
    """返回所有用户表的表名（排除 SQLite 内部表 sqlite_*）。"""
    try:
        with closing(connect()) as conn:
            rows = conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            ).fetchall()
        return [row[0] for row in rows]
    except sqlite3.Error as exc:
        raise DatabaseError(f"读取表清单失败：{exc}") from exc


def get_schema() -> list[dict]:
    """返回所有用户表的列结构。

    返回：
        [{"table": "表名",
          "columns": [{"name": "列名", "type": "类型", "notnull": bool, "pk": bool}, ...]}, ...]
    """
    tables = list_tables()
    result: list[dict] = []
    try:
        with closing(connect()) as conn:
            for table in tables:
                cols = conn.execute(f'PRAGMA table_info("{table}")').fetchall()
                columns = [
                    {
                        "name": col["name"],
                        "type": col["type"] or "",
                        "notnull": bool(col["notnull"]),
                        "pk": bool(col["pk"]),
                    }
                    for col in cols
                ]
                result.append({"table": table, "columns": columns})
    except sqlite3.Error as exc:
        raise DatabaseError(f"读取表结构失败：{exc}") from exc
    return result


# 内部系统表：不面向"问数"与前端展示（默认排除）
INTERNAL_TABLES = {"history"}


def list_user_tables() -> list[str]:
    """返回面向用户的表名（排除内部表）。"""
    return [t for t in list_tables() if t not in INTERNAL_TABLES]


def get_user_schema() -> list[dict]:
    """返回面向用户的表结构（排除内部表），供 LLM 提示与前端展示使用。"""
    return [t for t in get_schema() if t["table"] not in INTERNAL_TABLES]
