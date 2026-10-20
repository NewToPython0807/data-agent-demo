"""导入后一致性检查（T13）。

上传完成后校验：
- 行数符合（覆盖=新行数；追加=原行数+新行数）
- 表结构（列名）与源数据一致
- 覆盖模式下抽查首行内容一致
"""
from __future__ import annotations

from app.db import execute_query
from app.schema import get_schema


def check_consistency(
    table: str,
    mode: str,
    new_row_count: int,
    previous_count: int,
    expected_columns: list[str],
    expected_first_row: list | None = None,
) -> dict:
    """返回一致性报告；调用方据此判断 row_count_ok 是否通过。"""
    actual = execute_query(f'SELECT COUNT(*) AS c FROM "{table}"')
    actual_rows = int(actual["rows"][0][0]) if actual["rows"] else 0
    expected_total = new_row_count if mode == "replace" else previous_count + new_row_count

    schema_map = {t["table"]: [c["name"] for c in t["columns"]] for t in get_schema()}
    actual_columns = schema_map.get(table, [])

    sample = execute_query(f'SELECT * FROM "{table}" LIMIT 1')
    sample_row = sample["rows"][0] if sample["rows"] else None

    first_row_ok = None
    if mode == "replace" and expected_first_row is not None and sample_row is not None:
        first_row_ok = list(expected_first_row) == sample_row

    return {
        "table": table,
        "mode": mode,
        "row_count_ok": actual_rows == expected_total,
        "expected_total": expected_total,
        "actual_rows": actual_rows,
        "columns_ok": actual_columns == expected_columns,
        "expected_columns": expected_columns,
        "actual_columns": actual_columns,
        "first_row_ok": first_row_ok,
        "sample_row": sample_row,
    }
