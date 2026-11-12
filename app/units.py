"""比率单位识别（V3.1-T12）。

约定：SQL 中比率类结果统一输出小数（0–1），前端负责格式化为百分比。
"""
from __future__ import annotations

PERCENT_HINTS = ("率", "占比", "比例", "百分比", "rate", "ratio", "pct", "percent")


def percentage_columns(columns: list[str], plan: dict | None = None) -> list[str]:
    """返回需要按百分比展示的列。"""
    metric_pct = {
        str(m.get("name"))
        for m in (plan or {}).get("metrics") or []
        if isinstance(m, dict) and any(h in str(m.get("name") or "") for h in PERCENT_HINTS)
    }
    out: list[str] = []
    for c in columns or []:
        name = str(c)
        if any(h in name for h in PERCENT_HINTS) or name in metric_pct:
            out.append(name)
    return out
