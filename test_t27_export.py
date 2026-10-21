"""T27 导出端到端测试（紧凑输出）：登录 → /api/export → 校验 CSV 与查询结果一致。"""
import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning)

import csv  # noqa: E402
import io  # noqa: E402
import sys  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402

from app.db import execute_query
from app.main import app

checks: list[tuple[str, bool]] = []


def check(name: str, ok: bool) -> None:
    checks.append((name, ok))


client = TestClient(app)
r = client.post("/api/login", json={"username": "admin", "password": "test123"})
check("登录", r.status_code == 200)

sql = "SELECT region_name, manager FROM regions ORDER BY id"
r = client.post("/api/export", json={"sql": sql})
content = r.content

check("导出返回 200", r.status_code == 200)
check("Content-Type 为 CSV", "text/csv" in r.headers.get("content-type", ""))
check("含 UTF-8 BOM", content.startswith(b"\xef\xbb\xbf"))

text = content.decode("utf-8-sig")
parsed = list(csv.reader(io.StringIO(text)))
expected = execute_query(sql)
expected_cols = expected["columns"]
expected_rows = [["" if v is None else str(v) for v in row] for row in expected["rows"]]

check("表头一致", parsed[0] == expected_cols)
check("数据行一致", parsed[1:] == expected_rows)

failed = [name for name, ok in checks if not ok]
print(f"{len(checks) - len(failed)}/{len(checks)} passed")
print("ALL PASS" if not failed else "FAILED: " + ", ".join(failed))
sys.exit(0 if not failed else 1)
