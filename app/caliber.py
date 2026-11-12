"""消费口径后置校验（V3.1-T10）。

判断问题是否有“消费”意图，以及 SQL 是否遗漏
`is_consumption_flag='Y'` / `is_reversal_flag='N'`。
仅做检测，不修改 SQL；重试逻辑在 T11。
"""
from __future__ import annotations

import re

# 消费意图关键词
CONSUMPTION_HINTS = ("消费", "交易", "刷卡", "金额", "活跃卡", "用卡量")
# 明确排除“消费”口径的关键词
EXCLUDE_HINTS = ("取现", "还款", "全部交易", "所有交易", "转账", "账单")


def has_consumption_intent(question: str) -> bool:
    """问题是否应按“消费口径”统计。"""
    q = (question or "").strip()
    if not q:
        return False
    if any(k in q for k in EXCLUDE_HINTS):
        return False
    return any(k in q for k in CONSUMPTION_HINTS)


def _flag_ok(sql: str, column: str, expected: tuple[str, ...]) -> bool:
    """检查 `column = 'Y'`（或 1）是否出现。"""
    m = re.search(rf"{column}\s*=\s*['\"]?([a-z01])", sql.lower())
    return bool(m and m.group(1) in expected)


def check_consumption(sql: str, question: str) -> dict | None:
    """返回缺失的消费口径；无缺失/不适用时返回 None。

    返回：{"missing": ["is_consumption_flag='Y'", ...], "message": "..."}
    """
    if not has_consumption_intent(question):
        return None
    s = (sql or "").strip()
    if not s:
        return None
    if "fct_transaction" not in s.lower():
        return None

    missing: list[str] = []
    if not _flag_ok(s, "is_consumption_flag", ("y", "1")):
        missing.append("is_consumption_flag='Y'")
    if not _flag_ok(s, "is_reversal_flag", ("n", "0")):
        missing.append("is_reversal_flag='N'")
    if not missing:
        return None
    return {
        "missing": missing,
        "message": "消费口径缺失：" + "、".join(missing),
    }
