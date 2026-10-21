"""语义层数据模型（T03）。

新增四张表，不修改 V1 已有表：
- table_meta       表级中文名 / 业务说明
- column_meta      字段级中文名 / 业务说明
- metrics          指标定义（名称 / 口径 / 说明 / 关联表字段 / 单位 / 适用维度）
- metric_history   指标变更历史（旧版本快照）

启动时幂等建表（CREATE TABLE IF NOT EXISTS）。
"""
from __future__ import annotations

from datetime import datetime

from app.db import execute_query, execute_statement

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

# 语义层四张表（用于校验与后续引用）
SEMANTIC_TABLES = ("table_meta", "column_meta", "metrics", "metric_history")


def init_semantic_tables() -> None:
    """幂等创建语义层四张表（不修改 V1 已有表与数据）。"""
    for sql in (_TABLE_META_SQL, _COLUMN_META_SQL, _METRICS_SQL, _METRIC_HISTORY_SQL):
        execute_statement(sql)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# 表 / 字段 中文名（T04）
# ---------------------------------------------------------------------------

def list_tables_with_meta() -> list[dict]:
    """用户数据表 + 表级中文名（按表名排序，排除内部表）。"""
    from app.schema import get_user_schema

    metas = {
        row[0]: {"cn_name": row[1], "description": row[2]}
        for row in execute_query(
            "SELECT table_name, cn_name, description FROM table_meta"
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
            }
        )
    return result


def upsert_table_meta(table_name: str, cn_name: str = "", description: str = "") -> dict:
    """新增或更新表级中文名。"""
    now = _now()
    execute_statement(
        """
        INSERT INTO table_meta (table_name, cn_name, description, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(table_name) DO UPDATE SET
            cn_name = excluded.cn_name,
            description = excluded.description,
            updated_at = excluded.updated_at
        """,
        (table_name, cn_name, description, now, now),
    )
    return {"table": table_name, "cn_name": cn_name, "description": description}


def list_columns_with_meta(table_name: str) -> list[dict]:
    """某表的字段列表 + 字段级中文名。"""
    from app.schema import get_user_schema

    columns = []
    for table in get_user_schema():
        if table["table"] == table_name:
            columns = table["columns"]
            break

    metas = {
        row[0]: {"cn_name": row[1], "description": row[2]}
        for row in execute_query(
            "SELECT column_name, cn_name, description FROM column_meta WHERE table_name = ?",
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
            }
        )
    return result


def upsert_column_meta(
    table_name: str, column_name: str, cn_name: str = "", description: str = ""
) -> dict:
    """新增或更新字段级中文名。"""
    now = _now()
    execute_statement(
        """
        INSERT INTO column_meta (table_name, column_name, cn_name, description, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(table_name, column_name) DO UPDATE SET
            cn_name = excluded.cn_name,
            description = excluded.description,
            updated_at = excluded.updated_at
        """,
        (table_name, column_name, cn_name, description, now, now),
    )
    return {
        "table": table_name,
        "column": column_name,
        "cn_name": cn_name,
        "description": description,
    }


# ---------------------------------------------------------------------------
# 完整语义层读取（T07）：表/字段中文名 + 指标
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
        row[0]: {"cn_name": row[1], "description": row[2]}
        for row in execute_query(
            "SELECT table_name, cn_name, description FROM table_meta"
        )["rows"]
    }
    column_metas = {
        (row[0], row[1]): {"cn_name": row[2], "description": row[3]}
        for row in execute_query(
            "SELECT table_name, column_name, cn_name, description FROM column_meta"
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
                }
            )
        tables.append(
            {
                "table": name,
                "cn_name": tmeta.get("cn_name", ""),
                "description": tmeta.get("description", ""),
                "columns": columns,
            }
        )

    return {"tables": tables, "metrics": list_metrics()}
