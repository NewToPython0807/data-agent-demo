"""上传校验与落库（T12）。

- 校验扩展名（.csv / .xlsx）、大小上限、空文件、模式。
- 内容先落临时文件，再调用 import_csv / import_excel，结束后清理临时文件。
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

from app.config import settings
from app.importer import DataImportError, import_csv, import_excel


class UploadError(Exception):
    """上传校验异常（可读提示）。"""


ALLOWED_EXT = {".csv", ".xlsx"}


def save_and_import(
    filename: str, content: bytes, mode: str = "replace", table: str | None = None
) -> dict:
    """校验并导入上传内容，返回导入结果。

    table 指定目标表名（追加到已有表时必须指定）；为空时按文件名生成。
    """
    if not filename:
        raise UploadError("缺少文件名")
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXT:
        raise UploadError("仅支持 .csv 或 .xlsx 文件")
    if mode not in ("replace", "append"):
        raise UploadError("模式必须是 replace（覆盖）或 append（追加）")
    if not content:
        raise UploadError("文件内容为空")

    limit = settings.max_upload_mb * 1024 * 1024
    if len(content) > limit:
        raise UploadError(f"文件超过 {settings.max_upload_mb}MB 限制")

    tmp_dir = settings.database_path_abs.parent / "uploads"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(suffix=ext, dir=str(tmp_dir))
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(content)
        target = table or filename
        if ext == ".csv":
            return import_csv(tmp_path, target, mode)
        return import_excel(tmp_path, target, mode)
    except DataImportError as exc:
        raise UploadError(str(exc)) from exc
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
