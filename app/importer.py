"""原始数据导入核心（T10：CSV；T11：Excel）。

- 用 pandas 解析 CSV / Excel(.xlsx)，写入 SQLite 单文件库。
- 模式：replace = 整表覆盖（默认）；append = 追加。
- 表名与列名做安全化处理（保留中文，替换空格/特殊字符），避免建表失败。
"""
from __future__ import annotations

import re
from contextlib import closing
from pathlib import Path

import pandas as pd

from app.consistency import check_consistency
from app.db import connect, execute_query


class DataImportError(Exception):
    """数据导入异常（可读提示）。"""


def sanitize_table_name(name: str) -> str:
    """由文件名生成安全表名：保留中文/字母/数字/下划线。"""
    stem = Path(str(name)).stem
    s = re.sub(r"[^\w]", "_", stem).strip("_")
    if not s:
        s = "imported"
    if s[0].isdigit():
        s = "t_" + s
    return s


def _sanitize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """列名安全化：保留中文与字母数字，替换空格/特殊字符，并去重。"""
    df = df.copy()
    new_cols = []
    for col in df.columns:
        s = re.sub(r"[^\w]", "_", str(col)).strip("_")
        if not s:
            s = "col"
        if s[0].isdigit():
            s = "c_" + s
        new_cols.append(s)

    seen: dict[str, int] = {}
    final = []
    for c in new_cols:
        if c in seen:
            seen[c] += 1
            final.append(f"{c}_{seen[c]}")
        else:
            seen[c] = 0
            final.append(c)
    df.columns = final
    return df


def _first_row(df: pd.DataFrame) -> list:
    """取首行并归一化（NaN → None、数值转为 Python 原生类型）。"""
    return [None if pd.isna(v) else v for v in df.iloc[0].astype(object).tolist()]


def _read_csv(path: Path) -> pd.DataFrame:
    """读取 CSV：优先 UTF-8(BOM)，失败回退 GBK（常见中文编码）。"""
    try:
        return pd.read_csv(path, encoding="utf-8-sig")
    except UnicodeDecodeError:
        return pd.read_csv(path, encoding="gbk")


def import_dataframe(df: pd.DataFrame, table_name: str, mode: str = "replace") -> dict:
    """把 DataFrame 写入 SQLite（replace=覆盖 / append=追加），并做一致性检查。"""
    if df is None or df.shape[1] == 0:
        raise DataImportError("文件没有有效列")
    if mode not in ("replace", "append"):
        raise DataImportError("模式必须是 replace（覆盖）或 append（追加）")
    df = _sanitize_columns(df)
    table = sanitize_table_name(table_name)

    previous_count = 0
    if mode == "append":
        existing = execute_query(f'SELECT COUNT(*) AS c FROM "{table}"')
        previous_count = int(existing["rows"][0][0]) if existing["rows"] else 0

    try:
        with closing(connect()) as conn:
            with conn:  # 成功提交、失败回滚
                df.to_sql(table, conn, if_exists=mode, index=False)
    except Exception as exc:  # noqa: BLE001 - 统一转成可读导入错误
        raise DataImportError(f"写入数据库失败：{exc}") from exc

    report = check_consistency(
        table,
        mode,
        new_row_count=int(len(df)),
        previous_count=previous_count,
        expected_columns=list(df.columns),
        expected_first_row=_first_row(df) if (mode == "replace" and len(df) > 0) else None,
    )
    if not report["row_count_ok"]:
        raise DataImportError(
            f"一致性校验失败：期望 {report['expected_total']} 行，实际 {report['actual_rows']} 行"
        )
    return {
        "table": table,
        "row_count": int(len(df)),
        "columns": list(df.columns),
        "consistency": report,
    }


def import_csv(path: str | Path, table_name: str | None = None, mode: str = "replace") -> dict:
    """解析 CSV 并导入。table_name 缺省时用文件名（去掉扩展名）作表名。"""
    path = Path(path)
    try:
        df = _read_csv(path)
    except Exception as exc:  # noqa: BLE001
        raise DataImportError(f"解析 CSV 失败：{exc}") from exc
    if df.shape[1] == 0:
        raise DataImportError("CSV 没有有效列")
    return import_dataframe(df, table_name or path.name, mode)


def import_excel(path: str | Path, table_name: str | None = None, mode: str = "replace") -> dict:
    """解析 .xlsx（第一个工作表）并导入。table_name 缺省时用文件名作表名。"""
    path = Path(path)
    try:
        df = pd.read_excel(path, engine="openpyxl")
    except Exception as exc:  # noqa: BLE001
        raise DataImportError(f"解析 Excel 失败：{exc}") from exc
    if df.shape[1] == 0:
        raise DataImportError("Excel 没有有效列")
    return import_dataframe(df, table_name or path.name, mode)
