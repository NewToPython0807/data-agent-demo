"""V3.1-T15 指标中文名/同义词/单位修正（幂等）。

运行：
    .venv\\Scripts\\python -m scripts.update_metric_meta_v31
"""
from __future__ import annotations

from datetime import datetime

from app.db import execute_query, execute_statement

SYNONYMS = {
    "txn_amount_total": "消费金额,交易金额,消费额,刷卡金额",
    "txn_count": "交易笔数,消费笔数,笔数",
    "active_card_count": "活跃卡,活跃卡量,用卡量",
    "credit_utilization_rate": "额度使用率,额度占用率,额度使用",
    "revolving_balance_total": "循环余额,循环信用,循环信用余额",
    "interest_income": "利息收入,利息",
    "repayment_rate": "还款率,回收率",
    "overdue_rate": "逾期率,不良率",
    "write_off_rate": "核销率,损失率",
    "points_issued": "积分发放,发分",
    "points_redeemed": "积分兑换,用分",
    "points_liability_balance": "积分负债,积分余额",
    "new_customer_count": "新增客户,获客数",
    "new_card_count": "新增发卡,发卡量",
    "activation_rate": "激活率,开卡率",
    "avg_credit_limit": "平均授信额度,户均授信,平均额度",
}

UNITS = {
    "txn_amount_total": "元",
    "txn_count": "笔",
    "active_card_count": "张",
    "credit_utilization_rate": "%",
    "revolving_balance_total": "元",
    "interest_income": "元",
    "repayment_rate": "%",
    "overdue_rate": "%",
    "write_off_rate": "%",
    "points_issued": "分",
    "points_redeemed": "分",
    "points_liability_balance": "分",
    "new_customer_count": "户",
    "new_card_count": "张",
    "activation_rate": "%",
    "avg_credit_limit": "元",
}

CONTEXT = {
    "avg_credit_limit": "按账户、期末快照",
}

DESCRIPTIONS = {
    "avg_credit_limit": "平均授信额度（按账户、期末快照）",
}


def main() -> None:
    now = datetime.now().isoformat(timespec="seconds")
    for name, synonyms in SYNONYMS.items():
        execute_statement(
            "UPDATE metrics SET synonyms = ?, unit = ?, updated_at = ? WHERE name = ?",
            (synonyms, UNITS.get(name, ""), now, name),
        )
        if name in CONTEXT:
            execute_statement(
                "UPDATE metrics SET context = ?, updated_at = ? WHERE name = ?",
                (CONTEXT[name], now, name),
            )
        if name in DESCRIPTIONS:
            execute_statement(
                "UPDATE metrics SET description = ?, updated_at = ? WHERE name = ?",
                (DESCRIPTIONS[name], now, name),
            )

    rows = execute_query(
        "SELECT name, synonyms, unit FROM metrics WHERE name IN ("
        + ",".join("?" for _ in SYNONYMS)
        + ") ORDER BY name",
        tuple(SYNONYMS),
    )["rows"]
    print(f"已更新 {len(rows)} 个指标：")
    for name, synonyms, unit in rows:
        print(f"  - {name} | {unit} | {synonyms}")


if __name__ == "__main__":
    main()
