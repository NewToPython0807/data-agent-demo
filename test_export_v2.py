"""T21 CSV 导出单元测试（紧凑输出）。"""
from app.export import build_csv

csv_text = build_csv(["地区", "销售额"], [["华东", 100], ["华南", None]])
csv_escape = build_csv(["a"], [["x,y"], ['he said "hi"']])

checks = [
    ("含 BOM", csv_text.startswith("\ufeff")),
    ("含表头", "地区,销售额" in csv_text),
    ("含数据", "华东,100" in csv_text),
    ("空值导出为空", "华南," in csv_text),
    ("逗号/引号正确转义", '"x,y"' in csv_escape and '"he said ""hi"""' in csv_escape),
]

failed = [name for name, ok in checks if not ok]
print(f"{len(checks) - len(failed)}/{len(checks)} passed")
print("ALL PASS" if not failed else "FAILED: " + ", ".join(failed))
