"""信用卡造数数据检核（详细输出 + 汇总）。

在 seed_credit_card.py 之后运行：
    .venv\\Scripts\\python test_seed_check.py
"""
from __future__ import annotations

import sys
from contextlib import closing

from app.db import connect

TABLES = [
    "dim_date", "dim_customer", "dim_account", "dim_card", "dim_card_product",
    "dim_merchant", "dim_transaction_type", "dim_channel", "dim_currency", "dim_status",
    "fct_transaction", "fct_billing_cycle", "fct_repayment", "fct_account_monthly_snapshot",
]

EXPECTED = {
    "dim_date": 1461, "dim_customer": 5000, "dim_account": 8000, "dim_card": 12000,
    "dim_card_product": 4, "dim_merchant": 500, "dim_transaction_type": 8,
    "dim_channel": 6, "dim_currency": 3, "dim_status": 8,
    "fct_transaction": 100000, "fct_billing_cycle": 50000,
    "fct_repayment": 30000, "fct_account_monthly_snapshot": 40000,
}

FK_CHECKS = [
    ("dim_account", "customer_sk", "dim_customer", "customer_sk"),
    ("dim_account", "account_status_code", "dim_status", "status_code"),
    ("dim_account", "base_currency_code", "dim_currency", "currency_code"),
    ("dim_card", "account_sk", "dim_account", "account_sk"),
    ("dim_card", "product_sk", "dim_card_product", "product_sk"),
    ("dim_card", "card_status_code", "dim_status", "status_code"),
    ("fct_transaction", "date_key", "dim_date", "date_key"),
    ("fct_transaction", "posting_date_key", "dim_date", "date_key"),
    ("fct_transaction", "customer_sk", "dim_customer", "customer_sk"),
    ("fct_transaction", "account_sk", "dim_account", "account_sk"),
    ("fct_transaction", "card_sk", "dim_card", "card_sk"),
    ("fct_transaction", "merchant_sk", "dim_merchant", "merchant_sk"),
    ("fct_transaction", "txn_type_code", "dim_transaction_type", "txn_type_code"),
    ("fct_transaction", "channel_code", "dim_channel", "channel_code"),
    ("fct_transaction", "currency_code", "dim_currency", "currency_code"),
    ("fct_billing_cycle", "account_sk", "dim_account", "account_sk"),
    ("fct_billing_cycle", "statement_date_key", "dim_date", "date_key"),
    ("fct_billing_cycle", "payment_due_date_key", "dim_date", "date_key"),
    ("fct_billing_cycle", "currency_code", "dim_currency", "currency_code"),
    ("fct_repayment", "account_sk", "dim_account", "account_sk"),
    ("fct_repayment", "date_key", "dim_date", "date_key"),
    ("fct_repayment", "channel_code", "dim_channel", "channel_code"),
    ("fct_repayment", "currency_code", "dim_currency", "currency_code"),
    ("fct_account_monthly_snapshot", "account_sk", "dim_account", "account_sk"),
    ("fct_account_monthly_snapshot", "month_end_date_key", "dim_date", "date_key"),
    ("fct_account_monthly_snapshot", "account_status_code", "dim_status", "status_code"),
]

results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  {detail}" if detail else ""))


def q1(conn, sql: str, params=()):
    return conn.execute(sql, params).fetchone()[0]


def main() -> int:
    with closing(connect()) as conn:
        # 1) 行数
        for t in TABLES:
            n = q1(conn, f'SELECT COUNT(*) FROM "{t}"')
            check(f"行数 {t}", n == EXPECTED[t], f"{n} / 期望 {EXPECTED[t]}")

        # 2) 主键唯一（单主键 + 复合主键）
        pk = {
            "dim_date": "date_key", "dim_customer": "customer_sk", "dim_account": "account_sk",
            "dim_card": "card_sk", "dim_card_product": "product_sk", "dim_merchant": "merchant_sk",
            "dim_transaction_type": "txn_type_code", "dim_channel": "channel_code",
            "dim_currency": "currency_code", "dim_status": "status_code",
            "fct_transaction": "transaction_id", "fct_repayment": "repayment_id",
        }
        for t, col in pk.items():
            n = q1(conn, f'SELECT COUNT(*) FROM (SELECT {col} FROM "{t}" GROUP BY {col} HAVING COUNT(*) > 1)')
            check(f"主键唯一 {t}", n == 0, f"重复 {n} 组")
        for t, cols in (("fct_billing_cycle", "account_sk, statement_date_key"),
                        ("fct_account_monthly_snapshot", "account_sk, month_end_date_key")):
            n = q1(conn, f'SELECT COUNT(*) FROM (SELECT {cols} FROM "{t}" GROUP BY {cols} HAVING COUNT(*) > 1)')
            check(f"复合主键唯一 {t}", n == 0, f"重复 {n} 组")

        # 3) 外键完整
        for left, lcol, right, rcol in FK_CHECKS:
            n = q1(conn, f'SELECT COUNT(*) FROM "{left}" WHERE {lcol} IS NOT NULL AND {lcol} NOT IN (SELECT {rcol} FROM "{right}")')
            check(f"外键 {left}.{lcol} -> {right}.{rcol}", n == 0, f"孤儿 {n}")

        # 4) 日期合法
        n = q1(conn, "SELECT COUNT(*) FROM dim_date WHERE date(full_date) IS NULL OR length(full_date) != 10")
        check("dim_date 日期合法", n == 0, f"非法 {n}")
        n = q1(conn, "SELECT COUNT(*) FROM dim_date WHERE date_key != CAST(REPLACE(full_date, '-', '') AS INTEGER)")
        check("dim_date 键与日期一致", n == 0, f"不一致 {n}")
        for t, col in (("dim_card", "issued_date"), ("dim_card", "expiry_date"),
                       ("dim_account", "open_date")):
            n = q1(conn, f'SELECT COUNT(*) FROM "{t}" WHERE date({col}) IS NULL')
            check(f"{t}.{col} 日期合法", n == 0, f"非法 {n}")

        # 5) 金额类型与符号
        n = q1(conn, "SELECT COUNT(*) FROM fct_transaction WHERE typeof(txn_amount) != 'real' OR typeof(txn_amount_cny) != 'real'")
        check("交易金额为数值", n == 0, f"非数值 {n}")
        n = q1(conn, "SELECT COUNT(*) FROM fct_transaction WHERE is_reversal_flag='N' AND txn_amount <= 0")
        check("非冲正金额 > 0", n == 0, f"违规 {n}")
        n = q1(conn, "SELECT COUNT(*) FROM fct_transaction WHERE is_reversal_flag='Y' AND txn_amount >= 0")
        check("冲正金额 < 0", n == 0, f"违规 {n}")

        # 6) 汇率与本位币换算
        n = q1(conn, "SELECT COUNT(*) FROM fct_transaction WHERE currency_code='CNY' AND ABS(fx_rate - 1.0) > 1e-9")
        check("CNY 汇率=1", n == 0, f"违规 {n}")
        n = q1(conn, "SELECT COUNT(*) FROM fct_transaction WHERE ABS(txn_amount_cny - ROUND(txn_amount * fx_rate, 2)) > 0.01")
        check("本位币金额 = 原币 × 汇率", n == 0, f"不符 {n}")

        # 7) 账单公式
        n = q1(conn, """
            SELECT COUNT(*) FROM fct_billing_cycle
            WHERE ABS(total_statement_amount - (beginning_cycle_balance + new_purchase_amount
                + cash_advance_amount + fee_amount + interest_amount)) > 0.01
        """)
        check("账单应还总额公式", n == 0, f"不符 {n}")

        # 8) 还款拆分
        n = q1(conn, """
            SELECT COUNT(*) FROM fct_repayment
            WHERE ABS(repayment_amount - (principal_portion + interest_portion + fee_portion + overpay_portion)) > 0.01
        """)
        check("还款金额拆分公式", n == 0, f"不符 {n}")

        # 9) 快照公式
        n = q1(conn, """
            SELECT COUNT(*) FROM fct_account_monthly_snapshot
            WHERE ABS(past_due_amount - (overdue_amount_m1 + overdue_amount_m2
                + overdue_amount_m3 + overdue_amount_m4p)) > 0.01
        """)
        check("逾期金额 = M1..M4+ 合计", n == 0, f"不符 {n}")
        n = q1(conn, """
            SELECT COUNT(*) FROM fct_account_monthly_snapshot
            WHERE ABS(available_credit - MAX(0, credit_limit - outstanding_balance)) > 0.01
        """)
        check("可用额度 = max(0, 额度-未偿)", n == 0, f"不符 {n}")

        # 10) 逾期阶段与天数一致
        n = q1(conn, """
            SELECT COUNT(*) FROM fct_account_monthly_snapshot WHERE
              (overdue_stage_code='M0' AND dpd_days != 0) OR
              (overdue_stage_code='M1' AND (dpd_days < 1 OR dpd_days > 30)) OR
              (overdue_stage_code='M2' AND (dpd_days < 31 OR dpd_days > 60)) OR
              (overdue_stage_code='M3' AND (dpd_days < 61 OR dpd_days > 90)) OR
              (overdue_stage_code='M4+' AND dpd_days <= 90)
        """)
        check("逾期阶段与 DPD 一致", n == 0, f"不一致 {n}")

        # 11) 冲正原交易存在
        n = q1(conn, """
            SELECT COUNT(*) FROM fct_transaction c
            WHERE c.original_transaction_id IS NOT NULL
              AND NOT EXISTS (SELECT 1 FROM fct_transaction p WHERE p.transaction_id = c.original_transaction_id)
        """)
        check("冲正原交易存在", n == 0, f"缺失 {n}")

        # 12) 主卡关系合法
        n = q1(conn, """
            SELECT COUNT(*) FROM dim_card c
            WHERE c.primary_card_sk IS NOT NULL AND NOT EXISTS (
              SELECT 1 FROM dim_card p
              WHERE p.card_sk = c.primary_card_sk AND p.account_sk = c.account_sk
                AND p.is_primary_card_flag = 'Y'
            )
        """)
        check("副卡主卡关系合法", n == 0, f"违规 {n}")

        # 13) 活跃卡数不超过账户卡数
        n = q1(conn, """
            SELECT COUNT(*) FROM (
              SELECT s.account_sk, s.active_card_count_in_acct,
                     (SELECT COUNT(*) FROM dim_card c WHERE c.account_sk = s.account_sk) AS n
              FROM fct_account_monthly_snapshot s
            ) WHERE active_card_count_in_acct > n
        """)
        check("活跃卡数 ≤ 账户卡数", n == 0, f"违规 {n}")

        # 14) 还款账单关联存在（业务关联）
        n = q1(conn, """
            SELECT COUNT(*) FROM fct_repayment r
            WHERE r.billing_cycle_id IS NOT NULL
              AND NOT EXISTS (SELECT 1 FROM fct_billing_cycle b WHERE b.billing_cycle_id = r.billing_cycle_id)
        """)
        check("还款账单关联存在", n == 0, f"缺失 {n}")

        # 15) 语义层
        table_names = "(" + ",".join("'%s'" % t for t in TABLES) + ")"
        n = q1(conn, f"SELECT COUNT(*) FROM table_meta WHERE table_name IN {table_names}")
        check("语义层表数", n == 14, f"{n} / 14")
        n = q1(conn, f"SELECT COUNT(*) FROM metrics WHERE name IN "
                     "('txn_amount_total','txn_count','active_card_count','credit_utilization_rate',"
                     "'revolving_balance_total','interest_income','repayment_rate','overdue_rate',"
                     "'write_off_rate','points_issued','points_redeemed','points_liability_balance',"
                     "'new_customer_count','new_card_count','activation_rate','avg_credit_limit')")
        check("语义层指标数", n == 16, f"{n} / 16")
        n = q1(conn, f"SELECT COUNT(*) FROM table_relations WHERE left_table IN {table_names}")
        check("表关系数", n >= 26, f"{n} / ≥26")
        n = q1(conn, f"SELECT COUNT(*) FROM column_meta WHERE table_name IN {table_names}")
        check("字段中文名数", n >= 150, f"{n} / ≥150")

    failed = [name for name, ok, _ in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} passed")
    print("ALL PASS" if not failed else "FAILED: " + ", ".join(failed))
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
