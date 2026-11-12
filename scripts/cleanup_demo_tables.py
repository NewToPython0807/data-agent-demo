"""V3.1-T14 清理演示/测试表（D5 B）。

- 物理删除 9 张测试表；
- 清理 table_meta / column_meta / table_relations；
- 删除“销售额”测试指标与变更历史；
- 清理 golden_sql 与 golden_queries.json 中的测试表引用；
- 执行前自动备份 data/agent.db（若备份不存在）。

运行（项目根目录）：
    .venv\\Scripts\\python -m scripts.cleanup_demo_tables
"""
from __future__ import annotations

import json
import shutil
from contextlib import closing
from pathlib import Path

from app.config import BASE_DIR, settings
from app.db import connect
from app.golden import init_golden_table
from app.semantic import init_semantic_tables

TEST_TABLES = [
    "test_sales",
    "test_customer",
    "cons",
    "big",
    "e2e_sales",
    "customers",
    "orders",
    "products",
    "regions",
]


def main() -> None:
    db_path = settings.database_path_abs
    backup = db_path.with_suffix(db_path.suffix + ".v3.0.bak")
    if db_path.is_file() and not backup.exists():
        shutil.copy2(db_path, backup)
        print(f"已备份数据库：{backup}")
    else:
        print(f"备份已存在或数据库不存在，跳过备份：{backup}")

    init_semantic_tables()
    init_golden_table()

    with closing(connect()) as conn:
        with conn:
            for table in TEST_TABLES:
                conn.execute(f'DROP TABLE IF EXISTS "{table}"')

            placeholders = ",".join("?" for _ in TEST_TABLES)
            conn.execute(
                f"DELETE FROM table_meta WHERE table_name IN ({placeholders})", TEST_TABLES
            )
            conn.execute(
                f"DELETE FROM column_meta WHERE table_name IN ({placeholders})", TEST_TABLES
            )
            conn.execute(
                f"DELETE FROM table_relations WHERE left_table IN ({placeholders}) "
                f"OR right_table IN ({placeholders})",
                TEST_TABLES + TEST_TABLES,
            )

            conn.execute(
                "DELETE FROM metric_history WHERE metric_id IN "
                "(SELECT id FROM metrics WHERE name = '销售额')"
            )
            conn.execute("DELETE FROM metrics WHERE name = '销售额'")

            for table in TEST_TABLES:
                conn.execute("DELETE FROM golden_sql WHERE sql LIKE ?", (f"%{table}%",))

    gq = BASE_DIR / "config" / "golden_queries.json"
    if gq.is_file():
        data = json.loads(gq.read_text(encoding="utf-8"))
        kept = [
            item
            for item in data
            if not any(
                t in (str(item.get("sql", "")) + str(item.get("question", "")))
                for t in TEST_TABLES
            )
        ]
        if len(kept) != len(data):
            gq.write_text(
                json.dumps(kept, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            print(f"golden_queries.json：{len(data)} -> {len(kept)} 条")
        else:
            print("golden_queries.json：无需清理")

    print("清理完成：9 张测试表、相关元数据、测试指标、golden 引用已移除。")


if __name__ == "__main__":
    main()
