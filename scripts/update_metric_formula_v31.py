"""V3.1-T21 指标口径修正（幂等）。

- write_off_rate：SUM/SUM
- 新增 cash_advance_amount（交易表口径）
- avg_credit_limit：按账户、最新月末快照
- repayment_rate：跨表 SUM/SUM（不走快路径）

运行（项目根目录）：
    .venv\\Scripts\\python -m scripts.update_metric_formula_v31
"""
from __future__ import annotations

from datetime import datetime

from app.db import execute_query, execute_statement

UPDATES = [
    (
        "write_off_rate",
        "SUM(write_off_amount_mtd) / SUM(outstanding_balance)",
        "核销率：周期核销/未偿余额",
        "fct_account_monthly_snapshot",
        "write_off_amount_mtd",
        "%",
        "日期/账户",
        "核销率,损失率",
        "SUM/SUM，周期口径",
    ),
    (
        "cash_advance_amount",
        "(SELECT SUM(txn_amount_cny) FROM fct_transaction WHERE txn_type_code='CASH_ADV' AND is_reversal_flag='N')",
        "取现金额：交易表 CASH_ADV 合计（剔除冲正）",
        "",
        "txn_amount_cny",
        "元",
        "日期/账户/卡",
        "取现金额,取现",
        "交易表口径；跨表公式不走快路径",
    ),
    (
        "avg_credit_limit",
        "(SELECT AVG(credit_limit) FROM fct_account_monthly_snapshot WHERE month_end_date_key = (SELECT MAX(month_end_date_key) FROM fct_account_monthly_snapshot))",
        "平均授信额度（按账户、最新月末快照）",
        "",
        "credit_limit",
        "元",
        "日期/账户",
        "平均授信额度,户均授信,平均额度",
        "按账户、最新月末快照",
    ),
    (
        "repayment_rate",
        "(SELECT SUM(repayment_amount - overpay_portion) FROM fct_repayment) / (SELECT SUM(total_statement_amount) FROM fct_billing_cycle)",
        "还款率：实际收回/到期账单",
        "",
        "",
        "%",
        "日期/账户",
        "还款率,回收率",
        "跨表比率；不走快路径",
    ),
]


def main() -> None:
    now = datetime.now().isoformat(timespec="seconds")
    for name, formula, desc, table_name, column_name, unit, dims, syn, ctx in UPDATES:
        exists = execute_query("SELECT id FROM metrics WHERE name = ?", (name,))["rows"]
        if exists:
            execute_statement(
                "UPDATE metrics SET formula = ?, description = ?, table_name = ?, column_name = ?, "
                "unit = ?, dimensions = ?, synonyms = ?, context = ?, updated_at = ? WHERE name = ?",
                (formula, desc, table_name, column_name, unit, dims, syn, ctx, now, name),
            )
        else:
            execute_statement(
                "INSERT INTO metrics (name, formula, description, table_name, column_name, unit, "
                "dimensions, synonyms, context, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (name, formula, desc, table_name, column_name, unit, dims, syn, ctx, now, now),
            )

    rows = execute_query(
        "SELECT name, formula, unit FROM metrics WHERE name IN (?, ?, ?, ?) ORDER BY name",
        ("write_off_rate", "cash_advance_amount", "avg_credit_limit", "repayment_rate"),
    )["rows"]
    print(f"已更新 {len(rows)} 个指标：")
    for name, formula, unit in rows:
        print(f"  - {name} | {unit} | {formula[:80]}")


if __name__ == "__main__":
    main()
