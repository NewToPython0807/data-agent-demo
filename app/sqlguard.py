"""只读保护（T16，决策 D6：直接拦截写操作）。

用户问数产生的 SQL 只允许 SELECT（含 WITH ... SELECT 的 CTE）。
任何写语句、多语句、未知前缀一律拦截并抛 SQLGuardError。
"""
from __future__ import annotations

import re


class SQLGuardError(Exception):
    """只读保护拒绝异常（可读提示）。"""


def _strip_comments(sql: str) -> str:
    """去掉注释：/* ... */ 与 -- ...（到行尾）。"""
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    sql = re.sub(r"--[^\n]*", " ", sql)
    return sql


def _strip_literals(sql: str) -> str:
    """去掉字符串字面量，避免字面量里的分号/关键字造成误判。"""
    sql = re.sub(r"'(?:[^']|'')*'", "''", sql)
    sql = re.sub(r'"(?:[^"]|"")*"', '""', sql)
    return sql


def _first_keyword(sql: str) -> str:
    m = re.match(r"\s*([A-Za-z]+)", sql)
    return m.group(1).upper() if m else ""


def assert_read_only(sql: str) -> None:
    """若非只读（或无法安全判断），抛 SQLGuardError 拦截。"""
    if not sql or not sql.strip():
        raise SQLGuardError("SQL 不能为空")

    s = _strip_comments(sql).strip().rstrip(";").strip()
    if not s:
        raise SQLGuardError("SQL 不能为空")

    no_lit = _strip_literals(s)
    if ";" in no_lit:
        raise SQLGuardError("只读保护：禁止执行多条语句")

    kw = _first_keyword(s)
    if kw == "SELECT":
        return
    if kw == "WITH":
        if re.search(
            r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|REPLACE|ATTACH|DETACH|VACUUM|PRAGMA)\b",
            no_lit,
            re.IGNORECASE,
        ):
            raise SQLGuardError("只读保护：禁止执行修改数据的语句")
        return

    raise SQLGuardError(f"只读保护：禁止执行 {kw or '未知'} 语句，仅允许 SELECT 查询")
