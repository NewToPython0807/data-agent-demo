"""T11 指标问数流程测试（紧凑输出：只打印汇总）。"""
from app.db import execute_statement
from app.metric_resolver import match_metrics, metric_sql, resolve_metric_question
from app.metrics import create_metric, delete_metric

m = create_metric("销售额", "SUM(销售额)", "总额", "test_sales", "销售额", "元", "地区/时间")
mid = m["id"]

checks = [
    ("匹配指标名", len(match_metrics("销售额是多少")) == 1),
    ("口径展开 SQL", metric_sql(m) == 'SELECT SUM(销售额) AS "销售额" FROM "test_sales"'),
    ("裸指标走快路径", resolve_metric_question("销售额") is not None),
    ("带条件不误判", resolve_metric_question("上个月销售额") is None),
]

delete_metric(mid)
execute_statement("DELETE FROM metric_history WHERE metric_id = ?", (mid,))

failed = [name for name, ok in checks if not ok]
print(f"{len(checks) - len(failed)}/{len(checks)} passed")
print("ALL PASS" if not failed else "FAILED: " + ", ".join(failed))
