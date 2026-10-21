"""结果导出 CSV（T21）。

把查询结果（columns + rows）转为 UTF-8 带 BOM 的 CSV 文本，Excel 可直接打开。
"""
from __future__ import annotations

import csv
import io
from typing import Any, Sequence

BOM = "\ufeff"


def build_csv(columns: Sequence[str], rows: Sequence[Sequence[Any]]) -> str:
    """生成 CSV 文本（含 UTF-8 BOM，首行为表头，空值导出为空）。"""
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(list(columns))
    for row in rows:
        writer.writerow(["" if v is None else v for v in row])
    return BOM + buf.getvalue()
