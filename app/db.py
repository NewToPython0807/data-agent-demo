"""SQLite 数据访问层（T05）。

- 仅依赖标准库 sqlite3，保持轻量。
- 每次操作独立建立连接：FastAPI 同步端点运行在线程池中，避免跨线程共享连接。
- 查询返回结构化结果（columns / rows / row_count）；
  所有 sqlite3 异常统一转为 DatabaseError，附可读中文提示。
- 本层是通用数据访问层：查询用 execute_query，写入（数据导入等内部操作用）
  execute_statement。用户提问产生的 SQL 的只读限制在 T16/T17 的接口层执行，
  不在此处放宽。
"""
from __future__ import annotations

import sqlite3
from contextlib import closing
from typing import Any, Sequence

from app.config import settings


class DatabaseError(Exception):
    """数据库操作异常：对外暴露可读的中文提示。"""


def _connect() -> sqlite3.Connection:
    """建立到 SQLite 单文件数据库的连接（确保父目录存在）。"""
    db_path = settings.database_path_abs
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=10)
    conn.row_factory = sqlite3.Row
    # 复杂查询（JOIN/排序/聚合）可能需要临时文件；改为内存临时表，
    # 避免系统临时目录不可写时出现 "unable to open database file"。
    conn.execute("PRAGMA temp_store = MEMORY")
    return conn


def connect() -> sqlite3.Connection:
    """对外暴露的连接工厂，供同包其它模块（如 schema）使用。"""
    return _connect()


def execute_query(sql: str, params: Sequence[Any] | None = None) -> dict:
    """执行查询，返回结构化结果。

    返回：
        {"columns": ["列1", "列2", ...],
         "rows": [[值1, 值2, ...], ...],
         "row_count": 行数}
    """
    sql = (sql or "").strip()
    if not sql:
        raise DatabaseError("SQL 不能为空")
    try:
        with closing(_connect()) as conn:
            cursor = conn.execute(sql, tuple(params or ()))
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            rows = [list(row) for row in cursor.fetchall()]
            return {"columns": columns, "rows": rows, "row_count": len(rows)}
    except sqlite3.Error as exc:
        raise DatabaseError(f"SQL 执行失败：{exc}") from exc


def execute_statement(sql: str, params: Sequence[Any] | None = None) -> dict:
    """执行写语句（DDL/DML，供数据导入等内部流程使用），成功自动提交、失败回滚。

    返回：
        {"row_count": 受影响行数}
    """
    sql = (sql or "").strip()
    if not sql:
        raise DatabaseError("SQL 不能为空")
    try:
        with closing(_connect()) as conn:
            with conn:  # 成功提交、异常回滚
                cursor = conn.execute(sql, tuple(params or ()))
                return {"row_count": cursor.rowcount if cursor.rowcount >= 0 else 0}
    except sqlite3.Error as exc:
        raise DatabaseError(f"SQL 执行失败：{exc}") from exc
