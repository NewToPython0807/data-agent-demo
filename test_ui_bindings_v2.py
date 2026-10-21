"""T20 前端联调静态检查（紧凑输出）：JS 引用的元素 ID 是否都在 HTML 定义、导航项是否齐全。"""
import re
import sys
from pathlib import Path

root = Path(__file__).resolve().parent
js = (root / "static" / "app.js").read_text(encoding="utf-8")
html = (root / "static" / "index.html").read_text(encoding="utf-8")

js_ids = set(re.findall(r'getElementById\("([^"]+)"\)', js))
html_ids = set(re.findall(r'id="([^"]+)"', html))
missing_ids = sorted(js_ids - html_ids)

views = set(re.findall(r'data-view="([^"]+)"', html))
expected_views = {"tables", "metrics", "history", "settings"}
missing_views = sorted(expected_views - views)

checks = [
    ("JS 引用的 ID 都在 HTML 中", not missing_ids),
    ("导航四项齐全", not missing_views),
]

print("引用但未定义:", missing_ids if missing_ids else "无")
print("缺失导航项:", missing_views if missing_views else "无")
failed = [name for name, ok in checks if not ok]
print(f"{len(checks) - len(failed)}/{len(checks)} passed")
print("ALL PASS" if not failed else "FAILED: " + ", ".join(failed))
sys.exit(0 if not failed else 1)
