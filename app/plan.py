"""查询计划解析（V3-T11）。

把模型返回的“【查询计划】JSON + 【SQL】”文本解析为结构化计划与 SQL。
解析失败时降级：plan=None，尽量提取 SQL。
"""
from __future__ import annotations

import json
import re


def _strip_fence(text: str) -> str:
    """去掉 ```json ... ``` 代码围栏与首尾空白。"""
    text = (text or "").strip()
    if not text.startswith("```"):
        return text
    lines = text.splitlines()
    if lines and lines[0].strip().startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _extract_sql(text: str) -> str:
    return _strip_fence(text)


def _parse_json(block: str) -> dict | None:
    """从文本中解析 JSON 对象（容忍代码围栏/前后杂字）。"""
    block = _strip_fence(block)
    if not block:
        return None
    try:
        data = json.loads(block)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        pass
    # 退而求其次：取第一个 { ... } 块
    start = block.find("{")
    end = block.rfind("}")
    if start != -1 and end > start:
        try:
            data = json.loads(block[start : end + 1])
            return data if isinstance(data, dict) else None
        except json.JSONDecodeError:
            return None
    return None


def _as_list(value) -> list:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, (str, int, float)):
        return [value]
    return []


def _normalize(plan: dict) -> dict:
    ca = plan.get("can_answer", True)
    if isinstance(ca, str):
        ca = ca.strip().lower() not in ("false", "0", "no", "否", "不能", "无法")
    return {
        "can_answer": bool(ca),
        "metrics": _as_list(plan.get("metrics")),
        "tables": _as_list(plan.get("tables")),
        "joins": _as_list(plan.get("joins")),
        "filters": _as_list(plan.get("filters")),
        "group_by": _as_list(plan.get("group_by")),
        "order_by": _as_list(plan.get("order_by")),
        "limit": plan.get("limit"),
        "assumptions": _as_list(plan.get("assumptions")),
        "ambiguities": _as_list(plan.get("ambiguities")),
        "missing": _as_list(plan.get("missing")),
        "reason": str(plan.get("reason") or ""),
    }


def parse_plan_response(text: str) -> dict:
    """解析模型输出，返回 {"plan": dict|None, "sql": str, "raw": str}。"""
    raw = (text or "").strip()
    if not raw:
        return {"plan": None, "sql": "", "raw": raw}

    plan = None
    sql = ""

    m = re.search(r"【查询计划】(.*?)【SQL】(.*)", raw, re.S)
    if m:
        plan = _parse_json(m.group(1))
        sql = _extract_sql(m.group(2))

    if plan is None:
        plan = _parse_json(raw)
    if not sql:
        sql = _extract_sql(raw)

    return {
        "plan": _normalize(plan) if isinstance(plan, dict) else None,
        "sql": sql,
        "raw": raw,
    }


def should_refuse(plan: dict | None) -> bool:
    """计划判定为“无法回答”时返回 True（V3-T12）。"""
    return bool(plan) and not plan.get("can_answer", True)


def build_refusal(plan: dict | None) -> str:
    """根据计划生成可读的拒答文案（避免重复“无法回答”）。"""
    if not plan:
        return "无法回答：问题所需的数据不在当前数据库中。"
    missing = [str(x) for x in (plan.get("missing") or []) if str(x).strip()]
    reason = str(plan.get("reason") or "").strip()
    if reason:
        text = reason
    elif missing:
        items = "、".join(missing)
        if any(len(m) > 20 for m in missing):
            text = items
        else:
            text = "缺少「" + items + "」相关数据或指标"
    else:
        text = "问题所需的数据不在当前数据库中"
    text = text.strip().rstrip("。")
    if text.startswith("无法回答"):
        return text + "。"
    return f"无法回答：{text}。"
