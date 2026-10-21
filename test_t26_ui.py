"""T26 三段式 UI 静态检查（紧凑输出）。"""
import re
import sys
from pathlib import Path

root = Path(__file__).resolve().parent
html = (root / "static" / "index.html").read_text(encoding="utf-8")
js = (root / "static" / "app.js").read_text(encoding="utf-8")
css = root / "static" / "app.css"

ids = re.findall(r'id="([^"]+)"', html)
dup = sorted({i for i in ids if ids.count(i) > 1})

nav_views = set(re.findall(r'data-view="([^"]+)"', html))
view_sections = set(re.findall(r'id="view-([^"]+)"', html))

required_ids = {
    "question", "ask", "sql-editor", "execute", "cancel",
    "result-table", "result-meta", "export-btn", "result-placeholder",
    "conversation-items", "table-list", "upload-btn", "upload-mode", "upload-table",
    "metric-list", "history-list", "settings-username",
}
missing_ids = sorted(required_ids - set(ids))

required_funcs = {
    "askQuestion", "executeSql", "renderResult", "renderConversation",
    "loadTables", "loadMetrics", "loadHistory",
}
missing_funcs = sorted(f for f in required_funcs if f"function {f}" not in js)

checks = [
    ("CSS 文件存在", css.exists()),
    ("静态资源已引用", "/static/app.js" in html and "/static/app.css" in html),
    ("无重复 ID", not dup),
    ("导航四项齐全", nav_views == {"tables", "metrics", "history", "settings"}),
    ("视图五种齐全", view_sections == {"ask", "tables", "metrics", "history", "settings"}),
    ("关键元素齐全", not missing_ids),
    ("关键函数齐全", not missing_funcs),
]

print("重复ID:", dup or "无")
print("缺失元素:", missing_ids or "无")
print("缺失函数:", missing_funcs or "无")
failed = [name for name, ok in checks if not ok]
print(f"{len(checks) - len(failed)}/{len(checks)} passed")
print("ALL PASS" if not failed else "FAILED: " + ", ".join(failed))
sys.exit(0 if not failed else 1)
