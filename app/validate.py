"""结果校验（V3-T18）：对查询结果做基础异常检查，返回可读提示。"""
from __future__ import annotations

MAX_ROWS_WARN = 5000


def check_result(result: dict) -> list[str]:
    """返回异常提示列表（空列表表示正常）。"""
    warnings: list[str] = []
    columns = result.get("columns") or []
    rows = result.get("rows") or []
    row_count = int(result.get("row_count") or len(rows))

    if row_count == 0:
        return ["没有符合条件的数据（结果为空）"]

    if not columns:
        return ["结果没有列信息"]

    for idx, name in enumerate(columns):
        if all((row[idx] if idx < len(row) else None) is None for row in rows):
            warnings.append(f"列「{name}」全为空")

    if row_count > MAX_ROWS_WARN:
        warnings.append(f"结果行数较多（{row_count} 行），建议加筛选条件")

    return warnings
