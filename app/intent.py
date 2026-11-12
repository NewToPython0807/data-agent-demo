"""意图分流（V3.1-T19）：敏感信息拒答、模糊问题澄清。"""
from __future__ import annotations

import re

SENSITIVE_HINTS = ("身份证", "密码", "手机号", "完整卡号", "卡号", "证件号", "cvv")
VAGUE_HINTS = (
    "重点地区", "重点", "帮我看看", "整体", "大概", "情况怎么样", "表现怎么样", "数据怎么样",
)
# 相对时间：没有明确年月时应先澄清基准
RELATIVE_HINTS = (
    "上个月", "本月", "下个月", "最近", "近期", "目前", "当前", "现在", "这几天",
    "本周", "今年", "去年", "年初", "年底", "年末", "月初", "月末",
)
# 模糊/歧义说法
BOUNDARY_VAGUE_HINTS = (
    "怎么样", "如何", "情况", "表现", "用了多少", "哪个", "哪一个", "活跃客户",
)
# 写操作/破坏性意图
DESTRUCTIVE_HINTS = (
    "删掉", "删除", "清空", "drop", "truncate", "delete", "insert", "alter", "改表", "写入",
)
PERIOD_PATTERN = re.compile(r"(19|20)\d{2}\s*年|\d{4}[-/]\d{1,2}|\d{1,2}\s*月")


def is_sensitive(question: str) -> bool:
    """是否涉及敏感信息（应直接拒答）。"""
    q = (question or "").lower()
    return any(k in q for k in SENSITIVE_HINTS)


def is_vague(question: str) -> bool:
    """是否范围/指标缺失但可通过澄清解决。"""
    q = (question or "").strip()
    return any(k in q for k in VAGUE_HINTS)


def is_destructive(question: str) -> bool:
    """是否包含删除/写入等写操作意图。"""
    q = (question or "").lower()
    return any(k in q for k in DESTRUCTIVE_HINTS)


def has_explicit_period(question: str) -> bool:
    """问题是否已带明确年月。"""
    return bool(PERIOD_PATTERN.search(question or ""))


def is_boundary(question: str) -> bool:
    """无明确时间/口径的边界问题：应先澄清，而不是自行假设。"""
    q = (question or "").strip()
    if not q or has_explicit_period(q):
        return False
    if any(k in q for k in RELATIVE_HINTS) or any(k in q for k in BOUNDARY_VAGUE_HINTS):
        return True
    # 裸指标（如“消费金额”“利息收入多少”）没有时间范围，先澄清
    from app.metric_resolver import _terms, match_metrics

    metrics = match_metrics(q)
    if len(metrics) == 1:
        bare = re.sub(r"(是多少|多少|合计|总计|一共|总共|呢)$", "", q).strip()
        if bare in _terms(metrics[0]):
            return True
    return False
