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
from app.db import DatabaseError, connect, execute_query


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


def _looks_utf16(head: bytes) -> str | None:
    """通过 0 字节分布判断是否为无 BOM 的 UTF-16，返回编码名或 None。"""
    if len(head) < 8:
        return None
    even = head[0::2]
    odd = head[1::2]
    n = min(len(even), len(odd))
    if n == 0:
        return None
    even_nulls = sum(1 for b in even if b == 0)
    odd_nulls = sum(1 for b in odd if b == 0)
    if odd_nulls / n > 0.3 and even_nulls / n < 0.05:
        return "utf-16-le"
    if even_nulls / n > 0.3 and odd_nulls / n < 0.05:
        return "utf-16-be"
    return None


def _read_csv(path: Path) -> pd.DataFrame:
    """读取 CSV：自动识别常见编码、伪 CSV（其实是 xlsx）与制表符分隔。"""

    def _read(enc: str) -> pd.DataFrame:
        df = pd.read_csv(path, encoding=enc)
        # 逗号只切出 1 列时，尝试制表符分隔（Excel「Unicode 文本」常见）
        if df.shape[1] == 1:
            df_tab = pd.read_csv(path, encoding=enc, sep="\t")
            if df_tab.shape[1] > 1:
                return df_tab
        return df

    with open(path, "rb") as f:
        head = f.read(64 * 1024)

    # 1) 其实是 Excel（ZIP 头 PK）
    if head[:2] == b"PK":
        return pd.read_excel(path, engine="openpyxl")
    # 2) BOM
    if head[:3] == b"\xef\xbb\xbf":
        return _read("utf-8-sig")
    if head[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return _read("utf-16")

    # 3) 常见编码依次尝试
    last_err: Exception | None = None
    for enc in ("utf-8", "gbk", "gb18030", "big5"):
        try:
            return _read(enc)
        except UnicodeError as exc:
            last_err = exc
            continue

    # 4) 疑似无 BOM 的 UTF-16
    enc16 = _looks_utf16(head)
    if enc16:
        try:
            return _read(enc16)
        except UnicodeError as exc:
            last_err = exc

    # 5) 兜底：容错替换（不抛错，个别非法字节会被替换为 �）
    try:
        return pd.read_csv(path, encoding="gb18030", encoding_errors="replace")
    except Exception:
        raise ValueError(
            f"无法识别文件编码（{last_err}），请将文件另存为 UTF-8 后重试，或改用 .xlsx"
        )


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
        try:
            existing = execute_query(f'SELECT COUNT(*) AS c FROM "{table}"')
            previous_count = int(existing["rows"][0][0]) if existing["rows"] else 0
        except DatabaseError:
            raise DataImportError(
                f"追加模式要求目标表「{table}」已存在，请先上传数据或改用「整表覆盖」"
            ) from None

        existing_cols = execute_query(f'PRAGMA table_info("{table}")')["rows"]
        existing_names = {r[1] for r in existing_cols}
        if existing_names and existing_names != set(df.columns):
            raise DataImportError(
                f"追加失败：文件列与目标表「{table}」不一致"
                f"（目标表：{sorted(existing_names)}，文件：{sorted(df.columns)}）"
            )

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
