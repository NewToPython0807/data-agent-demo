"""T28 回归测试（V1 功能在 V2 中不被破坏，紧凑输出，进程内 TestClient）。"""
import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning)

import sys  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402

from app.db import execute_statement
from app.main import app
from app.metrics import create_metric, delete_metric

checks: list[tuple[str, bool]] = []


def check(name: str, ok: bool) -> None:
    checks.append((name, ok))


client = TestClient(app)

# 1) 登录
r = client.post("/api/login", json={"username": "admin", "password": "test123"})
check("登录成功", r.status_code == 200)
r = client.post("/api/login", json={"username": "admin", "password": "wrong"})
check("错误密码被拒", r.status_code == 401)

# 2) 上传（覆盖）
csv1 = "回归列A,回归列B\n1,2\n3,4\n".encode("utf-8")
r = client.post("/api/upload", files={"file": ("t28_reg.csv", csv1, "text/csv")}, data={"mode": "replace"})
check("上传成功", r.status_code == 200 and r.json().get("table") == "t28_reg")

# 3) 表结构（排除内部表）
r = client.get("/api/schema")
tables = [t["table"] for t in r.json()]
check("表结构含新表", "t28_reg" in tables)
check("表结构排除内部表", "history" not in tables and "metrics" not in tables and "table_meta" not in tables)

# 4) 执行查询
r = client.post("/api/execute", json={"question": "回归", "sql": "SELECT * FROM t28_reg"})
check("执行查询(2行)", r.status_code == 200 and r.json().get("row_count") == 2)

# 5) 追加
csv2 = "回归列A,回归列B\n5,6\n".encode("utf-8")
r = client.post(
    "/api/upload",
    files={"file": ("t28_reg.csv", csv2, "text/csv")},
    data={"mode": "append", "table": "t28_reg"},
)
check("追加成功", r.status_code == 200)
r = client.post("/api/execute", json={"question": "回归", "sql": "SELECT COUNT(*) AS c FROM t28_reg"})
check("追加后 3 行", r.status_code == 200 and r.json()["rows"] == [[3]])

# 6) 只读保护
r = client.post("/api/execute", json={"question": "x", "sql": "DELETE FROM t28_reg"})
check("只读保护", r.status_code == 400)

# 7) 历史
r = client.get("/api/history")
check("历史记录", r.status_code == 200 and len(r.json()) >= 1)

# 8) 导出
r = client.post("/api/export", json={"sql": "SELECT * FROM t28_reg"})
check("导出 CSV", r.status_code == 200 and r.content.startswith(b"\xef\xbb\xbf"))

# 9) 指标问数快路径（不依赖 LLM 网络）
metric = create_metric("回归指标", "SUM(回归列A)", "回归", "t28_reg", "回归列A", "", "")
r = client.post("/api/ask", json={"question": "回归指标"})
check(
    "指标问数快路径",
    r.status_code == 200 and r.json().get("source") == "metric" and "SUM(回归列A)" in r.json().get("sql", ""),
)
delete_metric(metric["id"])

# 清理
execute_statement("DROP TABLE IF EXISTS t28_reg")

failed = [name for name, ok in checks if not ok]
print(f"{len(checks) - len(failed)}/{len(checks)} passed")
print("ALL PASS" if not failed else "FAILED: " + ", ".join(failed))
sys.exit(0 if not failed else 1)
