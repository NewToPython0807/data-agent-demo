"""T23 测试造数：生成 4 张关联表（含中文、空值、边界值、关联键），可重复运行。

表结构：
- regions   (5 行)     地区维度
- customers (1 万行)   客户，region_id 关联 regions
- products  (500 行)   商品
- orders    (5 万行)   订单，customer_id 关联 customers、product_id 关联 products
"""
import random
import sys
from contextlib import closing
from datetime import date, timedelta

import pandas as pd

from app.db import connect
from app.semantic import upsert_column_meta, upsert_table_meta

random.seed(42)

REGIONS = ["华东", "华南", "华北", "西南", "东北"]
LEVELS = ["普通", "银牌", "金牌", "钻石", None]
STATUSES = ["已完成", "已取消", "待支付", None]
CATEGORIES = ["电子产品", "服装", "食品", "家居"]

N_REGIONS = 5
N_CUSTOMERS = 10_000
N_PRODUCTS = 500
N_ORDERS = 100_000


def _date(start: date, days: int) -> str:
    return (start + timedelta(days=random.randint(0, days))).isoformat()


def build_tables() -> dict[str, pd.DataFrame]:
    regions = pd.DataFrame(
        {
            "id": range(1, N_REGIONS + 1),
            "region_name": REGIONS,
            "manager": [f"{r}负责人" for r in REGIONS],
        }
    )
    customers = pd.DataFrame(
        {
            "id": range(1, N_CUSTOMERS + 1),
            "name": [f"客户{i:05d}" for i in range(1, N_CUSTOMERS + 1)],
            "region_id": [random.randint(1, N_REGIONS) for _ in range(N_CUSTOMERS)],
            "level": [random.choice(LEVELS) for _ in range(N_CUSTOMERS)],
            "created_date": [_date(date(2024, 1, 1), 365) for _ in range(N_CUSTOMERS)],
        }
    )
    products = pd.DataFrame(
        {
            "id": range(1, N_PRODUCTS + 1),
            "name": [f"商品{i:04d}" for i in range(1, N_PRODUCTS + 1)],
            "category": [random.choice(CATEGORIES) for _ in range(N_PRODUCTS)],
            "price": [round(random.uniform(1, 9999), 2) for _ in range(N_PRODUCTS)],
        }
    )
    orders = pd.DataFrame(
        {
            "id": range(1, N_ORDERS + 1),
            "customer_id": [random.randint(1, N_CUSTOMERS) for _ in range(N_ORDERS)],
            "product_id": [random.randint(1, N_PRODUCTS) for _ in range(N_ORDERS)],
            "quantity": [random.randint(0, 100) for _ in range(N_ORDERS)],
            "amount": [round(random.uniform(0, 100000), 2) for _ in range(N_ORDERS)],
            "status": [random.choice(STATUSES) for _ in range(N_ORDERS)],
            "order_date": [_date(date(2024, 1, 1), 365) for _ in range(N_ORDERS)],
        }
    )
    return {"regions": regions, "customers": customers, "products": products, "orders": orders}


def set_semantic_meta() -> None:
    """给种子表补中文名与指标口径，便于语义层/问数测试。"""
    upsert_table_meta("regions", "地区表", "地区维度")
    upsert_table_meta("customers", "客户表", "客户基础信息")
    upsert_table_meta("products", "商品表", "商品信息")
    upsert_table_meta("orders", "订单表", "销售订单")

    upsert_column_meta("orders", "amount", "订单金额", "订单总金额")
    upsert_column_meta("orders", "quantity", "数量", "购买数量")
    upsert_column_meta("orders", "status", "状态", "订单状态")
    upsert_column_meta("customers", "region_id", "地区ID", "关联地区表")
    upsert_column_meta("customers", "level", "客户等级", "会员等级")


def main() -> None:
    tables = build_tables()
    with closing(connect()) as conn:
        with conn:
            for name, df in tables.items():
                df.to_sql(name, conn, if_exists="replace", index=False)
    set_semantic_meta()
    for name, df in tables.items():
        print(f"{name}: {len(df)} 行")


if __name__ == "__main__":
    sys.exit(main())
