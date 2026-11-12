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


# 实现细节/默认假设：不应打断用户（V3.1，D1 A）
IMPL_HINTS = (
    "is_", "flag", "date_key", "字段", "取值", "编码", "代理键", "入账",
    "y/n", "1/0", "默认", "全历史", "是否剔除", "格式",
)
# 业务歧义：可能改变结果，需要用户确认
BLOCKING_HINTS = (
    "时间范围", "时间口径", "时间基准", "统计周期", "指标定义", "口径定义", "口径",
    "统计范围", "维度定义", "定义不明", "是否包含", "范围", "哪个", "哪一个",
    "哪一种", "指哪", "还是", "是指",
)


def is_blocking(text: str) -> bool:
    """判断一条歧义是否应打断用户。

    实现细节/默认假设优先判为 assumption；仅业务歧义判为 blocking。
    """
    t = (text or "").lower()
    if not t.strip():
        return False
    if any(k in t for k in IMPL_HINTS):
        return False
    return any(k in t for k in BLOCKING_HINTS)


def _normalize_ambiguities(value) -> list[dict]:
    """把 strings / objects 统一为 [{"text", "level"}]。"""
    items = _as_list(value)
    out: list[dict] = []
    for item in items:
        if isinstance(item, dict):
            text = str(item.get("text") or item.get("ambiguity") or "").strip()
            level = str(item.get("level") or "").strip().lower()
        else:
            text = str(item).strip()
            level = ""
        if not text:
            continue
        if level not in ("blocking", "assumption"):
            level = "blocking" if is_blocking(text) else "assumption"
        out.append({"text": text, "level": level})
    return out


def split_ambiguities(plan: dict | None) -> tuple[list[str], list[str]]:
    """返回 (blocking_texts, assumption_texts)。"""
    if not plan:
        return [], []
    blocking: list[str] = []
    assumptions: list[str] = []
    for item in plan.get("ambiguities") or []:
        if isinstance(item, dict):
            text = str(item.get("text") or "").strip()
            level = str(
                item.get("level")
                or ("blocking" if is_blocking(text) else "assumption")
            ).lower()
        else:
            text = str(item).strip()
            level = "blocking" if is_blocking(text) else "assumption"
        if not text:
            continue
        (blocking if level == "blocking" else assumptions).append(text)
    return blocking, assumptions


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
        "ambiguities": _normalize_ambiguities(plan.get("ambiguities")),
        "missing": _as_list(plan.get("missing")),
        "reason": str(plan.get("reason") or ""),
    }


def normalize_plan(plan: dict | None) -> dict | None:
    """对外暴露的计划归一（供历史回读兼容旧字符串格式）。"""
    return _normalize(plan) if isinstance(plan, dict) else None


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
