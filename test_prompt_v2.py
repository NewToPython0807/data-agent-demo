"""T09 提示词注入语义测试（紧凑输出：只打印汇总）。"""
from app.db import execute_statement
from app.metrics import create_metric, delete_metric
from app.prompt import build_prompt, build_schema_text
from app.semantic import upsert_column_meta, upsert_table_meta

# 准备语义数据
upsert_table_meta("test_sales", "销售数据", "测试用销售表")
upsert_column_meta("test_sales", "销售额", "销售额", "金额")
metric = create_metric("销售额", "SUM(销售额)", "销售总额", "test_sales", "销售额", "元", "地区/时间")

schema_text = build_schema_text()
prompt = build_prompt("上个月销售额是多少")

checks = [
    ("schema 含表中文名", "销售数据" in schema_text),
    ("schema 含字段中文名", "中文名：销售额" in schema_text),
    ("schema 含指标口径", "销售额 = SUM(销售额)" in schema_text),
    ("schema 含单位与维度", "单位：元" in schema_text and "维度：地区/时间" in schema_text),
    ("prompt 含指标说明", "指标口径" in prompt),
    ("prompt 含用户问题", "上个月销售额是多少" in prompt),
]

# 清理测试指标（含历史）
delete_metric(metric["id"])
execute_statement("DELETE FROM metric_history WHERE metric_id = ?", (metric["id"],))

failed = [name for name, ok in checks if not ok]
print(f"{len(checks) - len(failed)}/{len(checks)} passed")
print("ALL PASS" if not failed else "FAILED: " + ", ".join(failed))
