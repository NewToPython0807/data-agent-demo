"""T12 复杂查询验收用例：JOIN / HAVING / 窗口函数（紧凑输出：只打印汇总）。

小样本数据 + 三类代表性 SQL，验证只读保护放行、执行结果正确。
（真实 LLM 生成效果在 T25 用造数实测。）
"""
import sys

from app.db import execute_query, execute_statement
from app.sqlguard import assert_read_only

results: list[tuple[str, bool]] = []


def check(name: str, ok: bool) -> None:
    results.append((name, ok))


# 准备小样本数据
execute_statement("DROP TABLE IF EXISTS t12_orders")
execute_statement("DROP TABLE IF EXISTS t12_regions")
execute_statement("CREATE TABLE t12_regions (id INTEGER PRIMARY KEY, region TEXT)")
execute_statement("CREATE TABLE t12_orders (id INTEGER PRIMARY KEY, region_id INTEGER, customer TEXT, amount INTEGER)")
execute_statement("INSERT INTO t12_regions (id, region) VALUES (1,'华东'),(2,'华南')")
execute_statement(
    "INSERT INTO t12_orders (id, region_id, customer, amount) VALUES "
    "(1,1,'A',100),(2,1,'B',200),(3,1,'C',300),(4,2,'D',50),(5,2,'E',80)"
)

# 1) JOIN：订单关联地区
sql_join = (
    "SELECT r.region, SUM(o.amount) AS total "
    "FROM t12_orders o JOIN t12_regions r ON o.region_id = r.id "
    "GROUP BY r.region ORDER BY r.region"
)
assert_read_only(sql_join)
r = execute_query(sql_join)
check("JOIN 结果", r["rows"] == [["华东", 600], ["华南", 130]])

# 2) HAVING：聚合后筛选
sql_having = (
    "SELECT r.region, SUM(o.amount) AS total "
    "FROM t12_orders o JOIN t12_regions r ON o.region_id = r.id "
    "GROUP BY r.region HAVING SUM(o.amount) > 200 ORDER BY r.region"
)
assert_read_only(sql_having)
r = execute_query(sql_having)
check("HAVING 结果", r["rows"] == [["华东", 600]])

# 3) 窗口函数：地区内按金额排名
sql_window = (
    "SELECT customer, amount, "
    "ROW_NUMBER() OVER (PARTITION BY region_id ORDER BY amount DESC) AS rn "
    "FROM t12_orders ORDER BY region_id, rn"
)
assert_read_only(sql_window)
r = execute_query(sql_window)
check(
    "窗口函数结果",
    r["rows"] == [["C", 300, 1], ["B", 200, 2], ["A", 100, 3], ["E", 80, 1], ["D", 50, 2]],
)

# 清理
execute_statement("DROP TABLE t12_orders")
execute_statement("DROP TABLE t12_regions")

failed = [name for name, ok in results if not ok]
print(f"{len(results) - len(failed)}/{len(results)} passed")
print("ALL PASS" if not failed else "FAILED: " + ", ".join(failed))
sys.exit(0 if not failed else 1)
