"""指标定义 CRUD 与变更历史（T05/T06，V3 增同义词）。

指标字段：名称、口径、说明、关联表/字段、单位、适用维度、同义词。
每次更新前，把旧版本快照写入 metric_history（可追溯口径变化）。
"""
from __future__ import annotations

from contextlib import closing
from datetime import datetime

from app.db import connect, execute_query, execute_statement

_SELECT_COLUMNS = (
    "id, name, formula, description, table_name, column_name, unit, dimensions, synonyms, created_at, updated_at"
)

_HISTORY_COLUMNS = (
    "id, metric_id, name, formula, description, table_name, column_name, unit, dimensions, synonyms, changed_at"
)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _row_to_dict(row) -> dict:
    return {
        "id": row[0],
        "name": row[1],
        "formula": row[2],
        "description": row[3],
        "table_name": row[4],
        "column_name": row[5],
        "unit": row[6],
        "dimensions": row[7],
        "synonyms": row[8],
        "created_at": row[9],
        "updated_at": row[10],
    }


def list_metrics() -> list[dict]:
    rows = execute_query(f"SELECT {_SELECT_COLUMNS} FROM metrics ORDER BY id")["rows"]
    return [_row_to_dict(r) for r in rows]


def get_metric(metric_id: int) -> dict | None:
    rows = execute_query(
        f"SELECT {_SELECT_COLUMNS} FROM metrics WHERE id = ?", (metric_id,)
    )["rows"]
    return _row_to_dict(rows[0]) if rows else None


def create_metric(
    name: str,
    formula: str,
    description: str = "",
    table_name: str = "",
    column_name: str = "",
    unit: str = "",
    dimensions: str = "",
    synonyms: str = "",
) -> dict:
    now = _now()
    with closing(connect()) as conn:
        with conn:
            cursor = conn.execute(
                "INSERT INTO metrics "
                "(name, formula, description, table_name, column_name, unit, dimensions, synonyms, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    name,
                    formula,
                    description,
                    table_name,
                    column_name,
                    unit,
                    dimensions,
                    synonyms,
                    now,
                    now,
                ),
            )
            new_id = int(cursor.lastrowid)
    return get_metric(new_id)


def _snapshot(metric: dict) -> None:
    """把指标旧版本快照写入 metric_history。"""
    execute_statement(
        "INSERT INTO metric_history "
        "(metric_id, name, formula, description, table_name, column_name, unit, dimensions, synonyms, changed_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            metric["id"],
            metric["name"],
            metric["formula"],
            metric["description"],
            metric["table_name"],
            metric["column_name"],
            metric["unit"],
            metric["dimensions"],
            metric.get("synonyms", ""),
            _now(),
        ),
    )


def update_metric(
    metric_id: int,
    name: str,
    formula: str,
    description: str = "",
    table_name: str = "",
    column_name: str = "",
    unit: str = "",
    dimensions: str = "",
    synonyms: str = "",
) -> dict | None:
    old = get_metric(metric_id)
    if old is None:
        return None
    _snapshot(old)  # 先快照旧版本，再更新

    now = _now()
    result = execute_statement(
        "UPDATE metrics SET name = ?, formula = ?, description = ?, table_name = ?, "
        "column_name = ?, unit = ?, dimensions = ?, synonyms = ?, updated_at = ? WHERE id = ?",
        (
            name,
            formula,
            description,
            table_name,
            column_name,
            unit,
            dimensions,
            synonyms,
            now,
            metric_id,
        ),
    )
    if result["row_count"] == 0:
        return None
    return get_metric(metric_id)


def list_metric_history(metric_id: int) -> list[dict]:
    """返回某指标的变更历史（旧版本快照，按时间倒序）。"""
    rows = execute_query(
        f"SELECT {_HISTORY_COLUMNS} FROM metric_history WHERE metric_id = ? ORDER BY id DESC",
        (metric_id,),
    )["rows"]
    return [
        {
            "id": r[0],
            "metric_id": r[1],
            "name": r[2],
            "formula": r[3],
            "description": r[4],
            "table_name": r[5],
            "column_name": r[6],
            "unit": r[7],
            "dimensions": r[8],
            "synonyms": r[9],
            "changed_at": r[10],
        }
        for r in rows
    ]


def delete_metric(metric_id: int) -> bool:
    return execute_statement("DELETE FROM metrics WHERE id = ?", (metric_id,))["row_count"] > 0
