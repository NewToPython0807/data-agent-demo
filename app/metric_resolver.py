"""指标问数流程（T11）。

- match_metrics：从问题中匹配出提到的指标。
- metric_sql：把指标按口径展开为 SQL（SELECT 口径 AS 指标名 FROM 关联表）。
- resolve_metric_question：裸指标问法（如“销售额”“销售额是多少”）直接返回展开 SQL，否则返回 None 交给 LLM。
"""
from __future__ import annotations

import re


def match_metrics(question: str) -> list[dict]:
    """返回问题中提到的指标（按指标名子串匹配）。"""
    from app.metrics import list_metrics

    q = question or ""
    if not q.strip():
        return []
    return [m for m in list_metrics() if m.get("name") and m["name"] in q]


def metric_sql(metric: dict) -> str:
    """把指标按口径展开为 SQL；缺少口径或关联表时返回空字符串。"""
    formula = (metric.get("formula") or "").strip()
    table = (metric.get("table_name") or "").strip()
    name = (metric.get("name") or "").strip().replace('"', '""')
    if not formula or not table:
        return ""
    return f'SELECT {formula} AS "{name}" FROM "{table}"'


def resolve_metric_question(question: str) -> str | None:
    """裸指标问法（如“销售额”“销售额是多少”）返回按口径展开的 SQL，否则 None。"""
    metrics = match_metrics(question)
    if len(metrics) != 1:
        return None
    metric = metrics[0]
    q = (question or "").strip().rstrip("?？").strip()
    q = re.sub(r"(是多少|多少|合计|总计|一共|总共)$", "", q).strip()
    if q != metric["name"]:
        return None
    return metric_sql(metric) or None
