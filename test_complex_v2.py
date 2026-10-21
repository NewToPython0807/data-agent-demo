"""T10 复杂查询提示策略测试（紧凑输出：只打印汇总）。"""
from app.prompt import build_prompt, build_table_relations_text

prompt = build_prompt("每个地区销售额排名前 3 的客户")

checks = [
    ("含 JOIN 策略", "JOIN" in prompt),
    ("含 HAVING 策略", "HAVING" in prompt),
    ("含窗口函数策略", "ROW_NUMBER" in prompt and "OVER" in prompt),
    ("表关系扩展点为预留(空)", build_table_relations_text() == ""),
    ("含用户问题", "每个地区销售额排名前 3 的客户" in prompt),
]

failed = [name for name, ok in checks if not ok]
print(f"{len(checks) - len(failed)}/{len(checks)} passed")
print("ALL PASS" if not failed else "FAILED: " + ", ".join(failed))
