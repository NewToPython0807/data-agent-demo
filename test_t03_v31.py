"""T03 澄清分级测试（详细输出 + 汇总）。"""
import sys
import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning)

import app.main as main_module  # noqa: E402
from app.main import app  # noqa: E402
from app.plan import is_blocking, parse_plan_response, split_ambiguities  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


def show(label, value):
    print(f"[{label}] {value}")


# 1) is_blocking 规则
cases = [
    ("未指定时间范围", True),
    ("is_consumption_flag 的取值未明确", False),
    ("默认统计全部历史", False),
    ("指标定义不清", True),
    ("date_key 用交易日还是入账日", False),
    ("统计范围不明确", True),
]
for text, expect in cases:
    got = is_blocking(text)
    show(f"is_blocking({text})", f"{got}（期望 {expect}）")

# 2) 字符串/对象归一
raw1 = """【查询计划】
{"can_answer": true, "ambiguities": ["未指定时间范围", "默认统计全部历史"]}
【SQL】
SELECT 1 AS v
"""
p1 = parse_plan_response(raw1)
show("字符串归一", p1["plan"]["ambiguities"])

raw2 = """【查询计划】
{"can_answer": true, "ambiguities": [{"text": "指标定义不清", "level": "blocking"}, {"text": "默认全历史", "level": "assumption"}]}
【SQL】
SELECT 1 AS v
"""
p2 = parse_plan_response(raw2)
show("对象保留", p2["plan"]["ambiguities"])

blocking, assumptions = split_ambiguities(p1["plan"])
show("拆分结果", {"blocking": blocking, "assumptions": assumptions})

# 3) /api/ask 路由：blocking 澄清、assumption 直接出 SQL
client = TestClient(app)
client.post("/api/login", json={"username": "admin", "password": "test123"})

BLOCK_RAW = (
    '【查询计划】\n{"can_answer": true, "ambiguities": [{"text": "统计范围不明确", "level": "blocking"}]}\n'
    "【SQL】\nSELECT 1 AS v\n"
)
ASSUME_RAW = (
    '【查询计划】\n{"can_answer": true, "ambiguities": [{"text": "默认统计全部历史", "level": "assumption"}], '
    '"assumptions": ["默认全历史"]}\n【SQL】\nSELECT 1 AS v\n'
)

original = main_module.generate_plan_text


def ask(raw: str, payload: dict) -> dict:
    main_module.generate_plan_text = lambda q, c=None: raw
    try:
        return client.post("/api/ask", json=payload).json()
    finally:
        main_module.generate_plan_text = original


r_block = ask(BLOCK_RAW, {"question": "测试问题"})
r_assume = ask(ASSUME_RAW, {"question": "测试问题"})
show("blocking 路由", {"clarify": r_block.get("clarify"), "sql": r_block.get("sql")})
show("assumption 路由", {"clarify": r_assume.get("clarify"), "sql": r_assume.get("sql")})

checks = [
    ("时间范围 blocking", is_blocking("未指定时间范围") is True),
    ("flag 非 blocking", is_blocking("is_consumption_flag 的取值未明确") is False),
    ("默认全历史非 blocking", is_blocking("默认统计全部历史") is False),
    ("指标定义 blocking", is_blocking("指标定义不清") is True),
    ("字符串归一为对象", all(isinstance(a, dict) for a in p1["plan"]["ambiguities"])),
    ("拆分 blocking", blocking == ["未指定时间范围"]),
    ("拆分 assumption", assumptions == ["默认统计全部历史"]),
    ("blocking 触发 clarify", r_block.get("clarify") is True),
    ("assumption 不澄清", not r_assume.get("clarify")),
    ("assumption 直接出 SQL", r_assume.get("sql") == "SELECT 1 AS v"),
]

failed = [name for name, ok in checks if not ok]
print(f"\n{len(checks) - len(failed)}/{len(checks)} passed")
print("ALL PASS" if not failed else "FAILED: " + ", ".join(failed))
sys.exit(0 if not failed else 1)
