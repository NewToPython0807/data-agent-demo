"""SQL 自动纠错（V3-T16）。

执行失败时把错误反馈给模型生成修正 SQL；只读校验通过且能执行才返回。
最终结果不自动执行：返回修正 SQL 交由用户审核后再执行。
"""
from __future__ import annotations

from app.config import settings
from app.db import DatabaseError, execute_query
from app.llm import LLMError, generate_correction
from app.sqlguard import SQLGuardError, assert_read_only


def correct_sql(question: str, sql: str, error: str) -> str | None:
    """尝试生成可执行的修正 SQL；无法修正时返回 None。"""
    attempts = max(1, int(settings.max_sql_corrections))
    for _ in range(attempts):
        try:
            candidate = generate_correction(question, sql, error)
        except LLMError:
            return None
        candidate = (candidate or "").strip()
        if not candidate or candidate == sql:
            continue
        try:
            assert_read_only(candidate)
            execute_query(candidate)  # 只读校验：确认能执行
        except (SQLGuardError, DatabaseError):
            continue
        return candidate
    return None
