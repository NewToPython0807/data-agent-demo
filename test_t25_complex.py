"""T25 复杂查询测试（造数 + 10 万行，紧凑输出）。

覆盖：JOIN 聚合、HAVING 筛选、窗口函数排名，并记录耗时。
运行前请先执行 seed_data_v2.py（orders 为 10 万行）。
"""
import time

from app.db import execute_query

checks: list[tuple[str, bool]] = []


def check(name: str, ok: bool) -> None:
    checks.append((name, ok))


orders_count = execute_query("SELECT COUNT(*) AS c FROM orders")["rows"][0][0]
check("orders 行数 >= 100000", orders_count >= 100_000)

# 1) JOIN 聚合：按地区汇总订单金额
sql_join = """
SELECT r.region_name AS 地区, COUNT(*) AS 订单数, ROUND(SUM(o.amount), 2) AS 总金额
FROM orders o
JOIN customers c ON o.customer_id = c.id
JOIN regions r ON c.region_id = r.id
GROUP BY r.region_name
ORDER BY r.region_name
"""
t0 = time.perf_counter()
r = execute_query(sql_join)
elapsed = time.perf_counter() - t0
check("JOIN 返回 5 个地区", r["row_count"] == 5)
check("JOIN 金额非负", all(row[2] >= 0 for row in r["rows"]))

# 2) HAVING 筛选
sql_having = """
SELECT r.region_name AS 地区, ROUND(SUM(o.amount), 2) AS 总金额
FROM orders o
JOIN customers c ON o.customer_id = c.id
JOIN regions r ON c.region_id = r.id
GROUP BY r.region_name
HAVING SUM(o.amount) > 1000000
ORDER BY 总金额 DESC
"""
r = execute_query(sql_having)
check("HAVING 结果均 > 1000000", all(row[1] > 1000000 for row in r["rows"]))

# 3) 窗口函数：地区金额排名
sql_window = """
WITH region_totals AS (
  SELECT r.region_name AS 地区, SUM(o.amount) AS 总金额
  FROM orders o
  JOIN customers c ON o.customer_id = c.id
  JOIN regions r ON c.region_id = r.id
  GROUP BY r.region_name
)
SELECT 地区, 总金额, ROW_NUMBER() OVER (ORDER BY 总金额 DESC) AS 排名
FROM region_totals ORDER BY 排名
"""
r = execute_query(sql_window)
check("窗口函数返回 5 行", r["row_count"] == 5)
check("排名为 1..5", [row[2] for row in r["rows"]] == [1, 2, 3, 4, 5])

print(f"orders={orders_count}，JOIN 耗时 {elapsed * 1000:.0f} ms")
failed = [name for name, ok in checks if not ok]
print(f"{len(checks) - len(failed)}/{len(checks)} passed")
print("ALL PASS" if not failed else "FAILED: " + ", ".join(failed))
