"""上传追加模式测试（紧凑输出：只打印汇总）。

覆盖：追加到指定表成功、追加到不存在表报错清晰、列不一致报错清晰。
"""
from app.db import execute_query, execute_statement
from app.upload import UploadError, save_and_import

execute_statement("DROP TABLE IF EXISTS t14_append")

csv1 = "地区,销售额\n华东,100\n华南,200\n".encode("utf-8")
save_and_import("base.csv", csv1, "replace", table="t14_append")

csv2 = "地区,销售额\n华北,300\n".encode("utf-8")
save_and_import("more.csv", csv2, "append", table="t14_append")
count = execute_query('SELECT COUNT(*) AS c FROM t14_append')["rows"][0][0]

err_missing = ""
try:
    save_and_import("x.csv", csv2, "append", table="no_such_table")
except UploadError as exc:
    err_missing = str(exc)

csv3 = "地区,金额\n华东,1\n".encode("utf-8")
err_mismatch = ""
try:
    save_and_import("bad.csv", csv3, "append", table="t14_append")
except UploadError as exc:
    err_mismatch = str(exc)

execute_statement("DROP TABLE t14_append")

checks = [
    ("追加到指定表成功(2+1=3)", count == 3),
    ("追加到不存在表报错清晰", "已存在" in err_missing),
    ("列不一致报错清晰", "不一致" in err_mismatch),
]

failed = [name for name, ok in checks if not ok]
print(f"{len(checks) - len(failed)}/{len(checks)} passed")
print("ALL PASS" if not failed else "FAILED: " + ", ".join(failed))
