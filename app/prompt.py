"""SQL 生成提示组装（T14）。

把用户数据表的表结构 + 用户问题，组装成发送给 DeepSeek 的提示内容。
"""
from __future__ import annotations

from app.config import settings
from app.schema import get_user_schema


def build_schema_text() -> str:
    """把用户数据表结构转成给 LLM 看的文本。"""
    schema = get_user_schema()
    if not schema:
        return "（当前数据库没有任何数据表）"
    lines = []
    for t in schema:
        cols = ", ".join(f"{c['name']} {c['type'] or 'TEXT'}" for c in t["columns"])
        lines.append(f"表 {t['table']}（列：{cols}）")
    return "\n".join(lines)


def build_prompt(question: str, context: list[dict] | None = None) -> str:
    """组装问数提示词；context 为最近若干轮 {"question","sql"}，用于多轮追问。"""
    schema_text = build_schema_text()

    ctx_text = ""
    if context:
        turns = context[-settings.multi_turn_context_rounds:]
        lines = []
        for i, turn in enumerate(turns, 1):
            lines.append(f"{i}. 问题：{turn.get('question', '')}\n   生成的 SQL：{turn.get('sql', '')}")
        ctx_text = "\n".join(lines)

    parts = [
        "你是一个 SQLite 数据库查询助手。请根据下面的数据库表结构，把用户的中文问题转换成一条 SQL 查询语句。",
        "",
        "要求：",
        "1. 只输出一条 SELECT 查询语句，不要输出任何解释、注释或多余文字。",
        "2. 不要使用 INSERT/UPDATE/DELETE/DROP/ALTER 等修改数据的语句。",
        "3. SQL 需符合 SQLite 语法；表名、列名要与结构完全一致。",
        "4. 如果问题是追问（如“再按地区分组”“只看华东”），请结合下方上下文理解意图。",
        "",
        "数据库表结构：",
        schema_text,
    ]
    if ctx_text:
        parts += ["", "之前的问答上下文：", ctx_text]
    parts += ["", f"用户问题：{question}", "", "SQL："]
    return "\n".join(parts)
