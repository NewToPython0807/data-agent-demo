"""SQL 生成提示组装（T07/T09：注入语义层）。

把表结构、字段中文名、指标口径、同义词、表关系、业务上下文，以及用户问题，
组装成发送给 DeepSeek 的提示内容。
"""
from __future__ import annotations

from app.config import settings
from app.golden import match_golden
from app.metric_resolver import match_metrics
from app.semantic import get_semantic_layer


def build_schema_text(layer: dict | None = None) -> str:
    """把语义层（表结构 + 中文名 + 同义词 + 上下文 + 弃用 + 指标口径）转成给 LLM 看的文本。"""
    layer = layer or get_semantic_layer()
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
        if t.get("synonyms"):
            extras.append(f"同义词：{t['synonyms']}")
        if t.get("description"):
            extras.append(f"说明：{t['description']}")
        if t.get("context"):
            extras.append(f"注意：{t['context']}")
        if t.get("is_deprecated"):
            extras.append("【已弃用】")
        if extras:
            head += f"（{'，'.join(extras)}）"
        lines.append(head)
        for c in t.get("columns", []):
            col = f"  - {c['column']} {c.get('type') or 'TEXT'}"
            cextras = []
            if c.get("cn_name"):
                cextras.append(f"中文名：{c['cn_name']}")
            if c.get("synonyms"):
                cextras.append(f"同义词：{c['synonyms']}")
            if c.get("description"):
                cextras.append(f"说明：{c['description']}")
            if c.get("context"):
                cextras.append(f"注意：{c['context']}")
            if c.get("is_deprecated"):
                cextras.append("【已弃用】")
            if cextras:
                col += f"（{'，'.join(cextras)}）"
            lines.append(col)

    if metrics:
        lines.append("")
        lines.append("【指标口径】")
        for m in metrics:
            item = f"  - {m['name']} = {m['formula']}"
            mextras = []
            if m.get("synonyms"):
                mextras.append(f"同义词：{m['synonyms']}")
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


def build_table_relations_text(layer: dict | None = None) -> str:
    """表关系（JOIN 键）文本，供提示词注入。"""
    relations = (layer or get_semantic_layer()).get("relations", [])
    if not relations:
        return ""
    lines = []
    for r in relations:
        line = f"- {r['left_table']}.{r['left_column']} = {r['right_table']}.{r['right_column']}"
        if r.get("description"):
            line += f"（{r['description']}）"
        lines.append(line)
    return "\n".join(lines)


def build_prompt(question: str, context: list[dict] | None = None) -> str:
    """组装问数提示词；context 为最近若干轮 {"question","sql"}，用于多轮追问。"""
    layer = get_semantic_layer()
    schema_text = build_schema_text(layer)

    ctx_text = ""
    if context:
        turns = context[-settings.multi_turn_context_rounds:]
        lines = []
        for i, turn in enumerate(turns, 1):
            lines.append(f"{i}. 问题：{turn.get('question', '')}\n   生成的 SQL：{turn.get('sql', '')}")
        ctx_text = "\n".join(lines)

    parts = [
        "你是一个 SQLite 数据库查询助手。请根据下面的数据表结构、字段中文名、同义词、"
        "指标口径与表关系，把用户的中文问题转换成一条 SQL 查询语句。",
        "",
        "要求：",
        "1. 只输出一条 SELECT 查询语句，不要输出任何解释、注释或多余文字。",
        "2. 不要使用 INSERT/UPDATE/DELETE/DROP/ALTER 等修改数据的语句。",
        "3. SQL 需符合 SQLite 语法；表名、列名要与结构完全一致。",
        "4. 如果问题是追问（如“再按地区分组”“只看华东”），请结合下方上下文理解意图。",
        "5. 如果问题涉及业务指标（如销售额），优先使用【指标口径】中定义的计算方式。",
        "6. 用户可能使用同义词/业务术语，请结合“同义词”字段理解。",
        "7. 标记【已弃用】的表/字段慎用；有更合适的新表时优先用新表。",
        "8. 复杂查询按以下规则处理：",
        "   - 多表关联：优先使用【表关系（JOIN 键定义）】中的关系；未定义时再根据表名/字段名推断，并写清 ON 条件。",
        "   - 聚合后筛选：先 GROUP BY 聚合，再用 HAVING 筛选聚合结果（不要用 WHERE 筛选聚合值）。",
        "   - 排名/窗口：使用窗口函数，如 ROW_NUMBER() OVER (PARTITION BY ... ORDER BY ...)、RANK()、SUM(...) OVER (...)。",
        "",
        "数据库表结构与语义：",
        schema_text,
    ]

    relations_text = build_table_relations_text(layer)
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


_PLAN_FIELDS = """{
  "can_answer": true,
  "metrics": [{"name": "指标名", "formula": "计算口径"}],
  "tables": ["表名"],
  "joins": ["表A.字段 = 表B.字段"],
  "filters": [{"column": "列名", "op": "=", "value": "值"}],
  "group_by": ["列名"],
  "order_by": ["列名 DESC"],
  "limit": null,
  "assumptions": ["你做的假设"],
  "ambiguities": ["需要用户澄清的歧义"],
  "missing": []
}"""


def build_plan_prompt(question: str, context: list[dict] | None = None) -> str:
    """组装“先计划、后 SQL”的提示词（V3-T10）。"""
    layer = get_semantic_layer()
    schema_text = build_schema_text(layer)
    relations_text = build_table_relations_text(layer)

    ctx_text = ""
    if context:
        turns = context[-settings.multi_turn_context_rounds:]
        lines = []
        for i, turn in enumerate(turns, 1):
            lines.append(f"{i}. 问题：{turn.get('question', '')}\n   生成的 SQL：{turn.get('sql', '')}")
        ctx_text = "\n".join(lines)

    parts = [
        "你是一个 SQLite 数据分析助手。请先分析问题并输出【查询计划】JSON，再输出【SQL】。",
        "",
        "输出格式（严格）：",
        "【查询计划】",
        _PLAN_FIELDS,
        "【SQL】",
        "SELECT ...",
        "",
        "查询计划字段说明：",
        "- can_answer：问题所需的核心数据/指标是否在库中；不存在且无法推导时为 false。",
        "- metrics：使用的指标及口径。",
        "- tables：涉及的表。",
        "- joins：表间关联条件，优先使用下方“表关系（JOIN 键定义）”。",
        "- filters：过滤条件（列、运算符、值）。",
        "- group_by / order_by / limit：分组、排序、条数。",
        "- assumptions：你做的假设（如时间范围口径）。",
        "- ambiguities：需要用户澄清的歧义（如未指定时间、口径不清）。",
        "- missing：can_answer=false 时填写缺失的数据/指标。",
        "",
        "规则：",
        "1. 只输出上面两个部分，不要输出其它解释。",
        "2. 若 can_answer=false，【SQL】部分留空，并在 missing 写明缺什么。",
        "3. 不要编造表/字段；不确定的写入 assumptions 或 ambiguities。",
        "4. 同义词/业务术语结合“同义词”字段理解；标记【已弃用】的表/字段慎用。",
        "5. SQL 只读，一条 SELECT，符合 SQLite 语法。",
        "",
        "数据库表结构与语义：",
        schema_text,
    ]
    if relations_text:
        parts += ["", "表关系（JOIN 键定义）：", relations_text]

    matched = match_metrics(question)
    if matched:
        parts += ["", "问题中匹配到的指标："]
        for m in matched:
            ref = m.get("table_name", "")
            extra = f"（关联表：{ref}）" if ref else ""
            parts.append(f"  - {m['name']}：{m['formula']}{extra}")

    examples = match_golden(question)
    if examples:
        parts += ["", "参考示例（问题 → 正确 SQL）："]
        for ex in examples:
            parts.append(f"- 问题：{ex['question']}\n  SQL：{ex['sql']}")

    if ctx_text:
        parts += ["", "之前的问答上下文：", ctx_text]
    parts += ["", f"用户问题：{question}", ""]
    return "\n".join(parts)


def build_correction_prompt(question: str, sql: str, error: str) -> str:
    """SQL 执行失败时，要求模型给出修正后的 SQL（V3-T16）。"""
    layer = get_semantic_layer()
    schema_text = build_schema_text(layer)
    parts = [
        "下面这条 SQL 在 SQLite 中执行失败了，请根据错误信息和数据库结构给出修正后的 SQL。",
        "",
        "要求：",
        "1. 只输出一条修正后的 SELECT 语句，不要解释。",
        "2. 只能使用下方表结构中真实存在的表名/列名。",
        "3. 不要使用写操作（INSERT/UPDATE/DELETE/DROP/ALTER）。",
        "",
        "数据库表结构与语义：",
        schema_text,
        "",
        f"用户问题：{question}",
        "",
        "原 SQL：",
        sql,
        "",
        "错误信息：",
        error,
        "",
        "修正后的 SQL：",
    ]
    return "\n".join(parts)
