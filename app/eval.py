"""Golden queries 回归（V3-T22）。

用法：
    python -m app.eval          # 仅校验 golden SQL 与期望结果（离线）
    python -m app.eval --llm    # 用 LLM 生成 SQL 再比对（需要 DEEPSEEK_API_KEY）

golden_queries.json 每条：
    {
      "question": "问题",
      "sql": "期望 SQL",
      "expected": 标量 | 行列表 | null,   # null 表示只校验可执行
      "tolerance": 0.01
    }
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.config import BASE_DIR
from app.db import execute_query
from app.sqlguard import assert_read_only

GOLDEN_FILE = BASE_DIR / "golden_queries.json"


def _load() -> list[dict]:
    if not GOLDEN_FILE.is_file():
        return []
    return json.loads(GOLDEN_FILE.read_text(encoding="utf-8"))


def _compare(actual: dict, expected, tolerance: float) -> bool:
    """比对查询结果与期望：null 跳过；数字按容差；列表逐行比较。"""
    if expected is None:
        return True
    if isinstance(expected, (int, float)) and not isinstance(expected, bool):
        cell = actual["rows"][0][0] if actual["rows"] and actual["rows"][0] else None
        try:
            return abs(float(cell) - float(expected)) <= tolerance
        except (TypeError, ValueError):
            return False
    return [list(r) for r in actual["rows"]] == [list(r) for r in expected]


def golden_stats() -> dict:
    """返回 golden 集的通过情况（不打印，供统计接口使用）。"""
    items = _load()
    passed = 0
    for item in items:
        try:
            assert_read_only(item.get("sql", ""))
            result = execute_query(item["sql"])
            if _compare(result, item.get("expected"), float(item.get("tolerance", 0.01))):
                passed += 1
        except Exception:  # noqa: BLE001
            continue
    return {"total": len(items), "passed": passed}


def run(use_llm: bool = False) -> int:
    items = _load()
    if not items:
        print(f"未找到或为空：{GOLDEN_FILE}")
        return 1
    passed = 0
    for i, item in enumerate(items, 1):
        question = item.get("question", "")
        sql = item.get("sql", "")
        expected = item.get("expected")
        tolerance = float(item.get("tolerance", 0.01))
        try:
            if use_llm:
                from app.llm import generate_sql

                sql = generate_sql(question)
            assert_read_only(sql)
            result = execute_query(sql)
            ok = _compare(result, expected, tolerance)
        except Exception as exc:  # noqa: BLE001 - 单项失败不影响其它项
            print(f"[{i}] FAIL {question} -> {exc}")
            continue
        if ok:
            passed += 1
            print(f"[{i}] PASS {question}")
        else:
            print(f"[{i}] FAIL {question} -> 结果不符：{result['rows'][:3]}")
    total = len(items)
    rate = (passed / total * 100) if total else 0
    print(f"\n{passed}/{total} passed（{rate:.0f}%）")
    return 0 if passed == total else 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Golden queries 回归")
    parser.add_argument("--llm", action="store_true", help="用 LLM 生成 SQL 再比对")
    args = parser.parse_args()
    sys.exit(run(args.llm))


if __name__ == "__main__":
    main()
