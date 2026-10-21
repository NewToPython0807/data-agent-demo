"""T08 语义层端到端测试（紧凑输出：只打印汇总，便于控制上下文）。"""
import sys

from app.db import execute_statement
from app.metrics import (
    create_metric,
    delete_metric,
    get_metric,
    list_metric_history,
    update_metric,
)
from app.semantic import (
    get_semantic_layer,
    list_columns_with_meta,
    list_tables_with_meta,
    upsert_column_meta,
    upsert_table_meta,
)

checks: list[tuple[str, bool]] = []


def check(name: str, ok: bool) -> None:
    checks.append((name, ok))


# 1) 表/字段中文名
upsert_table_meta("test_sales", "销售数据", "测试用")
upsert_column_meta("test_sales", "销售额", "销售额", "金额")
tables = {t["table"]: t for t in list_tables_with_meta()}
check("表中文名保存", tables.get("test_sales", {}).get("cn_name") == "销售数据")
cols = {c["column"]: c for c in list_columns_with_meta("test_sales")}
check("字段中文名保存", cols.get("销售额", {}).get("cn_name") == "销售额")

# 2) 指标 CRUD + 变更历史
m = create_metric("销售额", "SUM(销售额)", "旧口径", "test_sales", "销售额", "元", "地区/时间")
mid = m["id"]
check("指标创建", mid > 0)
update_metric(mid, "销售额", "SUM(销售额)", "新口径", "test_sales", "销售额", "元", "地区/时间/渠道")
check("指标更新", get_metric(mid)["description"] == "新口径")
history = list_metric_history(mid)
check("变更历史保留旧版本", len(history) == 1 and history[0]["description"] == "旧口径")

# 3) 完整语义层
layer = get_semantic_layer()
check("语义层含表", any(t["table"] == "test_sales" for t in layer["tables"]))
check("语义层含指标", isinstance(layer["metrics"], list))
internal = {"history", "table_meta", "column_meta", "metrics", "metric_history"}
check("内部表已排除", all(t["table"] not in internal for t in layer["tables"]))

# 清理测试数据（指标 + 其历史）
delete_metric(mid)
execute_statement("DELETE FROM metric_history WHERE metric_id = ?", (mid,))

failed = [name for name, ok in checks if not ok]
print(f"{len(checks) - len(failed)}/{len(checks)} passed")
print("ALL PASS" if not failed else "FAILED: " + ", ".join(failed))
sys.exit(1 if failed else 0)
