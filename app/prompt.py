"""SQL 生成提示组装（T09：注入语义层）。

把用户数据表的表结构、字段中文名、指标口径，以及用户问题，组装成发送给 DeepSeek 的提示内容。
"""
from __future__ import annotations

from app.config import settings
from app.metric_resolver import match_metrics
from app.semantic import get_semantic_layer


def build_schema_text() -> str:
    """把语义层（表结构 + 字段中文名 + 指标口径）转成给 LLM 看的文本。"""
    layer = get_semantic_layer()
    tables = layer.get("tables", [])
    metrics = layer.get("metrics", [])

    if not tables:
        return "（当前数据库没有任何数据表）"

    lines = ["【数据表】"]
    for t in tables:
        head = f"表 {t['table']}"
        extras = []
        if t.get("cn_name"):
            extras.append(f"中文名：{t['cn_name']}")
        if t.get("description"):
            extras.append(f"说明：{t['description']}")
        if extras:
            head += f"（{'，'.join(extras)}）"
        lines.append(head)
        for c in t.get("columns", []):
            col = f"  - {c['column']} {c.get('type') or 'TEXT'}"
            cextras = []
            if c.get("cn_name"):
                cextras.append(f"中文名：{c['cn_name']}")
            if c.get("description"):
                cextras.append(f"说明：{c['description']}")
            if cextras:
                col += f"（{'，'.join(cextras)}）"
            lines.append(col)

    if metrics:
        lines.append("")
        lines.append("【指标口径】")
        for m in metrics:
            item = f"  - {m['name']} = {m['formula']}"
            mextras = []
            if m.get("description"):
                mextras.append(f"说明：{m['description']}")
            if m.get("unit"):
                mextras.append(f"单位：{m['unit']}")
            if m.get("dimensions"):
                mextras.append(f"维度：{m['dimensions']}")
            if m.get("table_name"):
                ref = m["table_name"] + (f".{m['column_name']}" if m.get("column_name") else "")
                mextras.append(f"关联：{ref}")
            if mextras:
                item += f"（{'，'.join(mextras)}）"
            lines.append(item)

    return "\n".join(lines)


def build_table_relations_text() -> str:
    """预留扩展点：表关系定义文本（本版未启用，返回空字符串）。

    后续版本若增加「表关系定义」模块，可在此返回形如
        - 表A.字段 = 表B.字段
    的内容，供提示词注入 JOIN 键。
    """
    return ""


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
        "你是一个 SQLite 数据库查询助手。请根据下面的数据表结构、字段中文名和指标口径，"
        "把用户的中文问题转换成一条 SQL 查询语句。",
        "",
        "要求：",
        "1. 只输出一条 SELECT 查询语句，不要输出任何解释、注释或多余文字。",
        "2. 不要使用 INSERT/UPDATE/DELETE/DROP/ALTER 等修改数据的语句。",
        "3. SQL 需符合 SQLite 语法；表名、列名要与结构完全一致。",
        "4. 如果问题是追问（如“再按地区分组”“只看华东”），请结合下方上下文理解意图。",
        "5. 如果问题涉及业务指标（如销售额），优先使用【指标口径】中定义的计算方式。",
        "6. 复杂查询按以下规则处理：",
        "   - 多表关联：需要多张表时使用显式 JOIN，关联键根据表名/字段名推断（如同名业务字段：地区、id、日期等），并写清 ON 条件。",
        "   - 聚合后筛选：先 GROUP BY 聚合，再用 HAVING 筛选聚合结果（不要用 WHERE 筛选聚合值）。",
        "   - 排名/窗口：使用窗口函数，如 ROW_NUMBER() OVER (PARTITION BY ... ORDER BY ...)、RANK()、SUM(...) OVER (...)。",
        "",
        "数据库表结构与语义：",
        schema_text,
    ]

    relations_text = build_table_relations_text()
    if relations_text:
        parts += ["", "表关系（JOIN 键定义）：", relations_text]

    matched = match_metrics(question)
    if matched:
        parts += ["", "问题中匹配到的指标："]
        for m in matched:
            ref = m.get("table_name", "")
            extra = f"（关联表：{ref}）" if ref else ""
            parts.append(f"  - {m['name']}：{m['formula']}{extra}")

    if ctx_text:
        parts += ["", "之前的问答上下文：", ctx_text]
    parts += ["", f"用户问题：{question}", "", "SQL："]
    return "\n".join(parts)
