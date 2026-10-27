"""信用卡维度模型 → Data Agent 语义层落地（V3 造数配套）。

写入 table_meta / column_meta / metrics / table_relations，使造数完成后
agent 立即拥有 14 张表的中文名、字段中文名、16 个指标口径与表关系。
"""
from __future__ import annotations

from datetime import datetime

TABLE_META = [
    ("dim_date", "日期维度", "自然日粒度，含财务日历与节假日"),
    ("dim_customer", "客户维度", "持卡人（自然人）粒度"),
    ("dim_account", "账户维度", "信用卡账户粒度"),
    ("dim_card", "卡片维度", "单张卡粒度，含主副卡关系"),
    ("dim_card_product", "卡产品维度", "卡产品 SKU"),
    ("dim_merchant", "商户维度", "受理商户"),
    ("dim_transaction_type", "交易类型维度", "交易类型与口径开关"),
    ("dim_channel", "渠道维度", "交易渠道"),
    ("dim_currency", "币种维度", "ISO 4217 币种"),
    ("dim_status", "状态维度", "账户/卡片状态"),
    ("fct_transaction", "交易事实表", "单笔交易/授权记录"),
    ("fct_billing_cycle", "账单事实表", "单账户单账单周期"),
    ("fct_repayment", "还款事实表", "单笔还款入账记录"),
    ("fct_account_monthly_snapshot", "账户月末快照", "每账户每月末状态"),
]

COLUMN_CN = {
    "dim_date": {
        "date_key": "日期智能键", "full_date": "自然日期", "year_num": "年份",
        "quarter_num": "季度", "month_num": "月份", "month_name": "年月标签",
        "week_of_year_num": "年内周序号", "weekday_num": "星期序号",
        "is_weekend_flag": "是否周末", "is_month_end_flag": "是否月末",
        "is_quarter_end_flag": "是否季末", "is_year_end_flag": "是否年末",
        "fiscal_year_num": "财务年", "fiscal_month_num": "财务月",
        "fiscal_quarter_num": "财务季度", "is_holiday_flag": "是否节假日",
        "holiday_name": "节假日名称",
    },
    "dim_customer": {
        "customer_sk": "客户代理键", "customer_id": "客户号", "customer_name_masked": "客户姓名(脱敏)",
        "gender_code": "性别", "birth_date": "出生日期", "cert_type_code": "证件类型",
        "cert_no_masked": "证件号(脱敏)", "mobile_masked": "手机号(脱敏)",
        "customer_level_code": "客户等级", "occupation_code": "职业代码",
        "income_band_code": "收入区间", "marital_status_code": "婚姻状况",
        "city_code": "城市代码", "province_code": "省份代码",
        "risk_rating_code": "风险等级", "kyc_level_code": "KYC等级",
        "is_staff_flag": "是否本行员工", "entry_date": "建档日期",
        "valid_from": "SCD2生效时间", "valid_to": "SCD2失效时间", "is_current_flag": "当前有效标志",
    },
    "dim_account": {
        "account_sk": "账户代理键", "account_id": "信用账户号", "customer_sk": "客户代理键",
        "account_type_code": "账户类型", "open_date": "开户日期", "close_date": "销户日期",
        "base_currency_code": "账户主币种", "statement_day_num": "账单日",
        "payment_due_days": "免息还款期天数", "account_status_code": "账户状态",
        "valid_from": "SCD2生效时间", "valid_to": "SCD2失效时间", "is_current_flag": "当前有效标志",
    },
    "dim_card": {
        "card_sk": "卡片代理键", "card_no_masked": "卡号(脱敏)", "account_sk": "所属账户",
        "product_sk": "卡产品", "card_medium_code": "卡介质", "issued_date": "制卡日期",
        "activated_date": "激活日期", "expiry_date": "卡片有效期",
        "card_status_code": "卡片状态", "card_credit_limit": "卡片子额度",
        "is_primary_card_flag": "是否主卡", "primary_card_sk": "主卡代理键",
        "valid_from": "SCD2生效时间", "valid_to": "SCD2失效时间", "is_current_flag": "当前有效标志",
    },
    "dim_card_product": {
        "product_sk": "产品代理键", "product_id": "产品代码", "product_name": "产品名称",
        "product_level_code": "产品等级", "card_network_code": "卡组织",
        "annual_fee_amount": "年费金额", "annual_fee_waiver_rule": "年费减免规则",
        "grace_period_days": "免息期天数", "interest_rate_apr": "年化利率",
        "min_payment_rate": "最低还款比例", "points_earn_rate": "积分累计比例",
        "foreign_txn_fee_rate": "货币转换费率", "currency_scope_code": "币种范围",
        "launch_date": "上线日期", "is_active_flag": "是否在售",
    },
    "dim_merchant": {
        "merchant_sk": "商户代理键", "merchant_id": "商户编号", "merchant_name": "商户名称",
        "mcc_code": "商户类别码", "mcc_category_desc": "MCC大类", "industry_code": "行业代码",
        "city_code": "城市代码", "province_code": "省份代码",
        "is_online_flag": "是否线上", "acquiring_institution_code": "收单机构",
    },
    "dim_transaction_type": {
        "txn_type_code": "交易类型代码", "txn_type_name": "交易类型名称",
        "is_consumption_flag": "是否消费口径", "is_financing_flag": "是否融资类",
        "is_fee_flag": "是否费用类", "is_interest_flag": "是否利息类",
        "is_reversal_type_flag": "是否冲正类", "earns_points_flag": "是否累计积分",
        "is_repayment_flag": "是否还款类",
    },
    "dim_channel": {
        "channel_code": "渠道代码", "channel_name": "渠道名称",
        "channel_group_code": "渠道大类", "is_ecommerce_flag": "是否电商渠道",
    },
    "dim_currency": {
        "currency_code": "币种代码", "currency_name": "币种名称",
        "currency_numeric_code": "币种数字码", "decimal_places": "小数位数",
        "is_local_currency_flag": "是否本位币",
    },
    "dim_status": {
        "status_code": "状态代码", "status_domain_code": "状态所属域",
        "status_name": "状态名称", "is_active_state_flag": "是否健康状态",
        "severity_order_num": "严重程度排序",
    },
    "fct_transaction": {
        "transaction_id": "交易流水号", "txn_timestamp": "交易时间",
        "date_key": "交易日期键", "posting_date_key": "入账日期键",
        "customer_sk": "客户", "account_sk": "账户", "card_sk": "卡片",
        "merchant_sk": "商户", "txn_type_code": "交易类型", "channel_code": "渠道",
        "currency_code": "交易币种", "auth_code": "授权码",
        "txn_amount": "交易原币金额", "txn_amount_cny": "交易本位币金额",
        "fx_rate": "汇率", "installment_term_num": "分期期数",
        "points_earned": "累计积分", "points_redeemed": "兑换积分",
        "is_reversal_flag": "是否冲正", "original_transaction_id": "原交易流水号",
    },
    "fct_billing_cycle": {
        "billing_cycle_id": "账单周期业务键", "account_sk": "账户",
        "statement_date_key": "账单日", "cycle_start_date_key": "周期起日",
        "cycle_end_date_key": "周期止日", "payment_due_date_key": "到期还款日",
        "currency_code": "账单币种", "beginning_cycle_balance": "上期结转余额",
        "new_purchase_amount": "本期新增消费", "cash_advance_amount": "本期取现金额",
        "fee_amount": "本期费用", "interest_amount": "本期利息",
        "total_statement_amount": "本期应还总额", "minimum_payment_amount": "最低还款额",
        "closing_cycle_balance": "本期结欠余额", "points_earned_in_cycle": "本期累计积分",
        "points_expired_in_cycle": "本期失效积分", "is_past_due_at_billing_flag": "出账时是否逾期",
    },
    "fct_repayment": {
        "repayment_id": "还款流水号", "account_sk": "账户", "date_key": "还款日期键",
        "billing_cycle_id": "冲抵账单周期", "channel_code": "还款渠道",
        "currency_code": "还款币种", "repayment_amount": "还款总金额",
        "principal_portion": "本金部分", "interest_portion": "利息部分",
        "fee_portion": "费用部分", "overpay_portion": "溢缴部分",
        "points_used_for_offset": "积分抵扣数", "is_on_time_flag": "是否按时",
        "is_partial_flag": "是否部分还款",
    },
    "fct_account_monthly_snapshot": {
        "account_sk": "账户", "month_end_date_key": "月末日期键",
        "account_status_code": "月末账户状态", "credit_limit": "月末授信额度",
        "available_credit": "月末可用额度", "outstanding_balance": "月末未偿余额",
        "revolving_balance": "月末循环余额", "cash_advance_balance": "月末取现余额",
        "current_cycle_due_amount": "当期应还金额", "past_due_amount": "月末逾期金额",
        "overdue_amount_m1": "逾期1-30天余额", "overdue_amount_m2": "逾期31-60天余额",
        "overdue_amount_m3": "逾期61-90天余额", "overdue_amount_m4p": "逾期90天以上余额",
        "dpd_days": "月末逾期天数", "overdue_stage_code": "月末逾期阶段",
        "points_balance": "月末积分余额", "interest_accrued_mtd": "本月累计利息",
        "fee_charged_mtd": "本月累计费用", "write_off_amount_mtd": "本月核销金额",
        "is_written_off_flag": "本月是否核销", "active_card_count_in_acct": "月末活跃卡数",
    },
}

METRICS = [
    ("txn_amount_total", "SUM(txn_amount_cny)", "消费交易金额：剔除冲正的消费交易本位币合计", "fct_transaction", "txn_amount_cny", "元", "日期/客户/账户/卡/商户/渠道", "消费金额,交易金额", "过滤 is_consumption_flag=Y 且 is_reversal_flag=N"),
    ("txn_count", "COUNT(transaction_id)", "消费交易笔数", "fct_transaction", "transaction_id", "笔", "日期/客户/账户/卡/渠道", "交易笔数,笔数", "口径同消费交易金额"),
    ("active_card_count", "COUNT(DISTINCT card_sk)", "活跃卡量：周期内至少 1 笔消费的卡数", "fct_transaction", "card_sk", "张", "日期/卡", "活跃卡,用卡量", "去重计数，跨期不可加"),
    ("credit_utilization_rate", "SUM(outstanding_balance) / SUM(credit_limit)", "额度使用率：期末未偿/授信", "fct_account_monthly_snapshot", "outstanding_balance", "%", "日期/账户", "额度使用率,额度占用", "取周期末快照；比率 SUM/SUM"),
    ("revolving_balance_total", "SUM(revolving_balance)", "循环余额：出账后未全额还清部分", "fct_account_monthly_snapshot", "revolving_balance", "元", "日期/账户", "循环余额,循环信用", "快照取期末值，跨期不可加"),
    ("interest_income", "SUM(interest_amount)", "利息收入：账单周期计收利息", "fct_billing_cycle", "interest_amount", "元", "日期/账户", "利息收入,利息", "以账单表为准"),
    ("repayment_rate", "(SELECT SUM(repayment_amount - overpay_portion) FROM fct_repayment) / (SELECT SUM(total_statement_amount) FROM fct_billing_cycle)", "还款率：实际收回/到期账单", "", "", "%", "日期/账户", "还款率,回收率", "跨表比率；由 LLM 按口径生成 SQL"),
    ("overdue_rate", "SUM(past_due_amount) / SUM(outstanding_balance)", "逾期率（余额口径）", "fct_account_monthly_snapshot", "past_due_amount", "%", "日期/账户", "逾期率,不良率", "取周期末快照；比率 SUM/SUM"),
    ("write_off_rate", "SUM(write_off_amount_mtd) / AVG(outstanding_balance)", "核销率：周期核销/平均未偿", "fct_account_monthly_snapshot", "write_off_amount_mtd", "%", "日期/账户", "核销率,损失率", "分母为周期内各月末平均"),
    ("points_issued", "SUM(points_earned)", "积分发放量", "fct_transaction", "points_earned", "分", "日期/客户/卡", "积分发放,发分", "交易级口径"),
    ("points_redeemed", "SUM(points_redeemed)", "积分兑换量", "fct_transaction", "points_redeemed", "分", "日期/客户/卡", "积分兑换,用分", "交易级口径"),
    ("points_liability_balance", "SUM(points_balance)", "积分负债余额", "fct_account_monthly_snapshot", "points_balance", "分", "日期/账户", "积分负债,积分余额", "快照取期末值"),
    ("new_customer_count", "COUNT(*)", "新增客户数：周期内新建档客户", "dim_customer", "customer_sk", "户", "日期", "新增客户,获客", "按 entry_date 过滤"),
    ("new_card_count", "COUNT(*)", "新增发卡量：周期内新发卡", "dim_card", "card_sk", "张", "日期", "新增发卡,发卡量", "按 issued_date 过滤"),
    ("activation_rate", "SUM(CASE WHEN activated_date IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*)", "激活率：已激活/已发卡", "dim_card", "activated_date", "%", "日期", "激活率,开卡率", "按发卡周期"),
    ("avg_credit_limit", "AVG(credit_limit)", "平均授信额度", "fct_account_monthly_snapshot", "credit_limit", "元", "日期/账户", "平均额度,授信额度", "取周期末快照"),
]

RELATIONS = [
    ("dim_account", "customer_sk", "dim_customer", "customer_sk", "账户-客户"),
    ("dim_account", "account_status_code", "dim_status", "status_code", "账户-状态"),
    ("dim_account", "base_currency_code", "dim_currency", "currency_code", "账户-币种"),
    ("dim_card", "account_sk", "dim_account", "account_sk", "卡片-账户"),
    ("dim_card", "product_sk", "dim_card_product", "product_sk", "卡片-产品"),
    ("dim_card", "card_status_code", "dim_status", "status_code", "卡片-状态"),
    ("fct_transaction", "date_key", "dim_date", "date_key", "交易-日期"),
    ("fct_transaction", "posting_date_key", "dim_date", "date_key", "交易-入账日期"),
    ("fct_transaction", "customer_sk", "dim_customer", "customer_sk", "交易-客户"),
    ("fct_transaction", "account_sk", "dim_account", "account_sk", "交易-账户"),
    ("fct_transaction", "card_sk", "dim_card", "card_sk", "交易-卡片"),
    ("fct_transaction", "merchant_sk", "dim_merchant", "merchant_sk", "交易-商户"),
    ("fct_transaction", "txn_type_code", "dim_transaction_type", "txn_type_code", "交易-类型"),
    ("fct_transaction", "channel_code", "dim_channel", "channel_code", "交易-渠道"),
    ("fct_transaction", "currency_code", "dim_currency", "currency_code", "交易-币种"),
    ("fct_billing_cycle", "account_sk", "dim_account", "account_sk", "账单-账户"),
    ("fct_billing_cycle", "statement_date_key", "dim_date", "date_key", "账单-账单日"),
    ("fct_billing_cycle", "payment_due_date_key", "dim_date", "date_key", "账单-到期日"),
    ("fct_billing_cycle", "currency_code", "dim_currency", "currency_code", "账单-币种"),
    ("fct_repayment", "account_sk", "dim_account", "account_sk", "还款-账户"),
    ("fct_repayment", "date_key", "dim_date", "date_key", "还款-日期"),
    ("fct_repayment", "channel_code", "dim_channel", "channel_code", "还款-渠道"),
    ("fct_repayment", "currency_code", "dim_currency", "currency_code", "还款-币种"),
    ("fct_account_monthly_snapshot", "account_sk", "dim_account", "account_sk", "快照-账户"),
    ("fct_account_monthly_snapshot", "month_end_date_key", "dim_date", "date_key", "快照-月末日期"),
    ("fct_account_monthly_snapshot", "account_status_code", "dim_status", "status_code", "快照-账户状态"),
]


def write_semantic_layer(conn) -> dict:
    """写入/更新语义层，返回计数。"""
    now = datetime.now().isoformat(timespec="seconds")

    for table, cn, desc in TABLE_META:
        conn.execute(
            "INSERT INTO table_meta (table_name, cn_name, description, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(table_name) DO UPDATE SET cn_name=excluded.cn_name, "
            "description=excluded.description, updated_at=excluded.updated_at",
            (table, cn, desc, now, now),
        )

    column_count = 0
    for table, cols in COLUMN_CN.items():
        for column, cn in cols.items():
            conn.execute(
                "INSERT INTO column_meta (table_name, column_name, cn_name, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(table_name, column_name) DO UPDATE SET cn_name=excluded.cn_name, "
                "updated_at=excluded.updated_at",
                (table, column, cn, now, now),
            )
            column_count += 1

    names = [m[0] for m in METRICS]
    placeholders = ",".join("?" for _ in names)
    conn.execute(f"DELETE FROM metrics WHERE name IN ({placeholders})", names)
    for name, formula, desc, table_name, column_name, unit, dimensions, synonyms, context in METRICS:
        conn.execute(
            "INSERT INTO metrics (name, formula, description, table_name, column_name, unit, dimensions, "
            "synonyms, context, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (name, formula, desc, table_name, column_name, unit, dimensions, synonyms, context, now, now),
        )

    tables = [t[0] for t in TABLE_META]
    placeholders = ",".join("?" for _ in tables)
    conn.execute(f"DELETE FROM table_relations WHERE left_table IN ({placeholders})", tables)
    for left_table, left_column, right_table, right_column, desc in RELATIONS:
        conn.execute(
            "INSERT INTO table_relations (left_table, left_column, right_table, right_column, description, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (left_table, left_column, right_table, right_column, desc, now),
        )

    return {
        "tables": len(TABLE_META),
        "columns": column_count,
        "metrics": len(METRICS),
        "relations": len(RELATIONS),
    }
