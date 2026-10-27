"""语义层数据模型（T03）。

新增四张表，不修改 V1 已有表：
- table_meta       表级中文名 / 业务说明
- column_meta      字段级中文名 / 业务说明
- metrics          指标定义（名称 / 口径 / 说明 / 关联表字段 / 单位 / 适用维度）
- metric_history   指标变更历史（旧版本快照）

启动时幂等建表（CREATE TABLE IF NOT EXISTS）。
"""
from __future__ import annotations

from contextlib import closing
from datetime import datetime

from app.db import connect, execute_query, execute_statement

_TABLE_META_SQL = """
CREATE TABLE IF NOT EXISTS table_meta (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    table_name TEXT NOT NULL UNIQUE,
    cn_name TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
"""

_COLUMN_META_SQL = """
CREATE TABLE IF NOT EXISTS column_meta (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    table_name TEXT NOT NULL,
    column_name TEXT NOT NULL,
    cn_name TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (table_name, column_name)
)
"""

_METRICS_SQL = """
CREATE TABLE IF NOT EXISTS metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    formula TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    table_name TEXT NOT NULL DEFAULT '',
    column_name TEXT NOT NULL DEFAULT '',
    unit TEXT NOT NULL DEFAULT '',
    dimensions TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
"""

_METRIC_HISTORY_SQL = """
CREATE TABLE IF NOT EXISTS metric_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    metric_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    formula TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    table_name TEXT NOT NULL DEFAULT '',
    column_name TEXT NOT NULL DEFAULT '',
    unit TEXT NOT NULL DEFAULT '',
    dimensions TEXT NOT NULL DEFAULT '',
    changed_at TEXT NOT NULL
)
"""

_TABLE_RELATIONS_SQL = """
CREATE TABLE IF NOT EXISTS table_relations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    left_table TEXT NOT NULL,
    left_column TEXT NOT NULL,
    right_table TEXT NOT NULL,
    right_column TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
)
"""

# 语义层五张表（用于校验与后续引用）
SEMANTIC_TABLES = (
    "table_meta",
    "column_meta",
    "metrics",
    "metric_history",
    "table_relations",
)


def _ensure_columns(table: str, columns: dict[str, str]) -> None:
    """幂等为表补列：columns 为 {列名: 列定义}（已存在则跳过）。"""
    existing = {row[1] for row in execute_query(f'PRAGMA table_info("{table}")')["rows"]}
    for name, ddl in columns.items():
        if name not in existing:
            execute_statement(f'ALTER TABLE "{table}" ADD COLUMN {name} {ddl}')


def init_semantic_tables() -> None:
    """幂等创建语义层表并补列（不修改 V1 已有表与数据）。"""
    for sql in (
        _TABLE_META_SQL,
        _COLUMN_META_SQL,
        _METRICS_SQL,
        _METRIC_HISTORY_SQL,
        _TABLE_RELATIONS_SQL,
    ):
        execute_statement(sql)

    # V3 增量列（幂等）：同义词 / 业务上下文 / 弃用标记
    _ensure_columns(
        "table_meta",
        {
            "synonyms": "TEXT NOT NULL DEFAULT ''",
            "context": "TEXT NOT NULL DEFAULT ''",
            "is_deprecated": "INTEGER NOT NULL DEFAULT 0",
        },
    )
    _ensure_columns(
        "column_meta",
        {
            "synonyms": "TEXT NOT NULL DEFAULT ''",
            "context": "TEXT NOT NULL DEFAULT ''",
            "is_deprecated": "INTEGER NOT NULL DEFAULT 0",
        },
    )
    _ensure_columns(
        "metrics",
        {
            "synonyms": "TEXT NOT NULL DEFAULT ''",
            "context": "TEXT NOT NULL DEFAULT ''",
        },
    )
    _ensure_columns(
        "metric_history",
        {"synonyms": "TEXT NOT NULL DEFAULT ''"},
    )


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# 表 / 字段 中文名（T04）
# ---------------------------------------------------------------------------

def list_tables_with_meta() -> list[dict]:
    """用户数据表 + 表级中文名 / 同义词（按表名排序，排除内部表）。"""
    from app.schema import get_user_schema

    metas = {
        row[0]: {
            "cn_name": row[1],
            "description": row[2],
            "synonyms": row[3],
            "context": row[4],
            "is_deprecated": row[5],
        }
        for row in execute_query(
            "SELECT table_name, cn_name, description, synonyms, context, is_deprecated FROM table_meta"
        )["rows"]
    }
    result = []
    for table in get_user_schema():
        name = table["table"]
        meta = metas.get(name, {})
        result.append(
            {
                "table": name,
                "cn_name": meta.get("cn_name", ""),
                "description": meta.get("description", ""),
                "synonyms": meta.get("synonyms", ""),
                "context": meta.get("context", ""),
                "is_deprecated": meta.get("is_deprecated", 0),
            }
        )
    return result


def upsert_table_meta(
    table_name: str,
    cn_name: str = "",
    description: str = "",
    synonyms: str = "",
    context: str = "",
    is_deprecated: int = 0,
) -> dict:
    """新增或更新表级中文名 / 同义词 / 业务上下文 / 弃用标记。"""
    now = _now()
    execute_statement(
        """
        INSERT INTO table_meta
            (table_name, cn_name, description, synonyms, context, is_deprecated, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(table_name) DO UPDATE SET
            cn_name = excluded.cn_name,
            description = excluded.description,
            synonyms = excluded.synonyms,
            context = excluded.context,
            is_deprecated = excluded.is_deprecated,
            updated_at = excluded.updated_at
        """,
        (
            table_name,
            cn_name,
            description,
            synonyms,
            context,
            is_deprecated,
            now,
            now,
        ),
    )
    return {
        "table": table_name,
        "cn_name": cn_name,
        "description": description,
        "synonyms": synonyms,
        "context": context,
        "is_deprecated": is_deprecated,
    }


def list_columns_with_meta(table_name: str) -> list[dict]:
    """某表的字段列表 + 字段级中文名 / 同义词。"""
    from app.schema import get_user_schema

    columns = []
    for table in get_user_schema():
        if table["table"] == table_name:
            columns = table["columns"]
            break

    metas = {
        row[0]: {
            "cn_name": row[1],
            "description": row[2],
            "synonyms": row[3],
            "context": row[4],
            "is_deprecated": row[5],
        }
        for row in execute_query(
            "SELECT column_name, cn_name, description, synonyms, context, is_deprecated "
            "FROM column_meta WHERE table_name = ?",
            (table_name,),
        )["rows"]
    }
    result = []
    for col in columns:
        name = col["name"]
        meta = metas.get(name, {})
        result.append(
            {
                "column": name,
                "type": col.get("type", ""),
                "cn_name": meta.get("cn_name", ""),
                "description": meta.get("description", ""),
                "synonyms": meta.get("synonyms", ""),
                "context": meta.get("context", ""),
                "is_deprecated": meta.get("is_deprecated", 0),
            }
        )
    return result


def upsert_column_meta(
    table_name: str,
    column_name: str,
    cn_name: str = "",
    description: str = "",
    synonyms: str = "",
    context: str = "",
    is_deprecated: int = 0,
) -> dict:
    """新增或更新字段级中文名 / 同义词 / 业务上下文 / 弃用标记。"""
    now = _now()
    execute_statement(
        """
        INSERT INTO column_meta
            (table_name, column_name, cn_name, description, synonyms, context, is_deprecated, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(table_name, column_name) DO UPDATE SET
            cn_name = excluded.cn_name,
            description = excluded.description,
            synonyms = excluded.synonyms,
            context = excluded.context,
            is_deprecated = excluded.is_deprecated,
            updated_at = excluded.updated_at
        """,
        (
            table_name,
            column_name,
            cn_name,
            description,
            synonyms,
            context,
            is_deprecated,
            now,
            now,
        ),
    )
    return {
        "table": table_name,
        "column": column_name,
        "cn_name": cn_name,
        "description": description,
        "synonyms": synonyms,
        "context": context,
        "is_deprecated": is_deprecated,
    }


# ---------------------------------------------------------------------------
# 表关系（T05）：JOIN 键
# ---------------------------------------------------------------------------

_RELATION_COLUMNS = (
    "id, left_table, left_column, right_table, right_column, description, created_at"
)


def _relation_to_dict(row) -> dict:
    return {
        "id": row[0],
        "left_table": row[1],
        "left_column": row[2],
        "right_table": row[3],
        "right_column": row[4],
        "description": row[5],
        "created_at": row[6],
    }


def list_relations() -> list[dict]:
    rows = execute_query(
        f"SELECT {_RELATION_COLUMNS} FROM table_relations ORDER BY id"
    )["rows"]
    return [_relation_to_dict(r) for r in rows]


def get_relation(relation_id: int) -> dict | None:
    rows = execute_query(
        f"SELECT {_RELATION_COLUMNS} FROM table_relations WHERE id = ?", (relation_id,)
    )["rows"]
    return _relation_to_dict(rows[0]) if rows else None


def create_relation(
    left_table: str,
    left_column: str,
    right_table: str,
    right_column: str,
    description: str = "",
) -> dict:
    now = _now()
    with closing(connect()) as conn:
        with conn:
            cursor = conn.execute(
                "INSERT INTO table_relations "
                "(left_table, left_column, right_table, right_column, description, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (left_table, left_column, right_table, right_column, description, now),
            )
            new_id = int(cursor.lastrowid)
    return get_relation(new_id)


def update_relation(
    relation_id: int,
    left_table: str,
    left_column: str,
    right_table: str,
    right_column: str,
    description: str = "",
) -> dict | None:
    result = execute_statement(
        "UPDATE table_relations SET left_table = ?, left_column = ?, right_table = ?, "
        "right_column = ?, description = ? WHERE id = ?",
        (left_table, left_column, right_table, right_column, description, relation_id),
    )
    if result["row_count"] == 0:
        return None
    return get_relation(relation_id)


def delete_relation(relation_id: int) -> bool:
    return (
        execute_statement("DELETE FROM table_relations WHERE id = ?", (relation_id,))[
            "row_count"
        ]
        > 0
    )


# ---------------------------------------------------------------------------
# 完整语义层读取（T07）：表/字段中文名 + 指标 + 表关系
# ---------------------------------------------------------------------------

def get_semantic_layer() -> dict:
    """返回完整语义层，供前端展示与问数提示使用。

    结构：
        {"tables": [{"table", "cn_name", "description",
                     "columns": [{"column", "type", "cn_name", "description"}]}],
         "metrics": [...]}
    """
    from app.metrics import list_metrics
    from app.schema import get_user_schema

    schema = get_user_schema()

    table_metas = {
        row[0]: {
            "cn_name": row[1],
            "description": row[2],
            "synonyms": row[3],
            "context": row[4],
            "is_deprecated": row[5],
        }
        for row in execute_query(
            "SELECT table_name, cn_name, description, synonyms, context, is_deprecated FROM table_meta"
        )["rows"]
    }
    column_metas = {
        (row[0], row[1]): {
            "cn_name": row[2],
            "description": row[3],
            "synonyms": row[4],
            "context": row[5],
            "is_deprecated": row[6],
        }
        for row in execute_query(
            "SELECT table_name, column_name, cn_name, description, synonyms, context, is_deprecated "
            "FROM column_meta"
        )["rows"]
    }

    tables = []
    for table in schema:
        name = table["table"]
        tmeta = table_metas.get(name, {})
        columns = []
        for col in table["columns"]:
            cmeta = column_metas.get((name, col["name"]), {})
            columns.append(
                {
                    "column": col["name"],
                    "type": col.get("type", ""),
                    "cn_name": cmeta.get("cn_name", ""),
                    "description": cmeta.get("description", ""),
                    "synonyms": cmeta.get("synonyms", ""),
                    "context": cmeta.get("context", ""),
                    "is_deprecated": cmeta.get("is_deprecated", 0),
                }
            )
        tables.append(
            {
                "table": name,
                "cn_name": tmeta.get("cn_name", ""),
                "description": tmeta.get("description", ""),
                "synonyms": tmeta.get("synonyms", ""),
                "context": tmeta.get("context", ""),
                "is_deprecated": tmeta.get("is_deprecated", 0),
                "columns": columns,
            }
        )

    return {
        "tables": tables,
        "metrics": list_metrics(),
        "relations": list_relations(),
    }
