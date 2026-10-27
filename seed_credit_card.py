"""信用卡维度模型造数脚本（V3）。

生成 10 张维度表 + 4 张事实表，写入当前 data/agent.db，并落地语义层。
运行：
    .venv\\Scripts\\python seed_credit_card.py

设计要点：
- 固定随机种子（42），可重复；
- 先生成维度、再生成事实，事实外键只从已存在维度键抽样；
- 金额 REAL、日期 TEXT；账单/还款/快照公式自洽；
- 造数后写入 table_meta / column_meta / metrics / table_relations。
"""
from __future__ import annotations

import random
from contextlib import closing
from datetime import date, datetime, timedelta

from app.db import connect
from seed_credit_card_semantic import write_semantic_layer

RNG = random.Random(42)

START = date(2023, 1, 1)
END = date(2026, 12, 31)

CUSTOMER_N = 5000
ACCOUNT_N = 8000
CARD_N = 12000
MERCHANT_N = 500
TXN_N = 100000
BILLING_N = 50000
REPAY_N = 30000
SNAPSHOT_N = 40000

SURNAMES = list("张王李赵刘陈杨黄周吴徐孙马朱胡郭何高林罗")
GIVENS = list("伟芳娜敏静丽强磊军洋勇艳杰娟涛明超秀霞平")
CITY_PROV = [
    ("110100", "110000"), ("310100", "310000"), ("440100", "440000"),
    ("440300", "440000"), ("330100", "330000"), ("320100", "320000"),
    ("510100", "510000"), ("420100", "420000"),
]
MCC = [
    ("5812", "餐饮"), ("5411", "超市"), ("5311", "百货"), ("4511", "航空"),
    ("7011", "酒店"), ("5999", "零售"), ("4111", "交通"), ("8011", "医疗"),
    ("5732", "电子"), ("5541", "加油"),
]
HOLIDAYS = {"01-01": "元旦", "05-01": "劳动节", "10-01": "国庆节", "10-02": "国庆节", "10-03": "国庆节"}

DDL = {
"dim_date": """CREATE TABLE IF NOT EXISTS dim_date (
    date_key INTEGER PRIMARY KEY, full_date TEXT NOT NULL, year_num INTEGER NOT NULL,
    quarter_num INTEGER NOT NULL, month_num INTEGER NOT NULL, month_name TEXT NOT NULL,
    week_of_year_num INTEGER NOT NULL, weekday_num INTEGER NOT NULL, is_weekend_flag TEXT NOT NULL,
    is_month_end_flag TEXT NOT NULL, is_quarter_end_flag TEXT NOT NULL, is_year_end_flag TEXT NOT NULL,
    fiscal_year_num INTEGER NOT NULL, fiscal_month_num INTEGER NOT NULL, fiscal_quarter_num INTEGER NOT NULL,
    is_holiday_flag TEXT NOT NULL, holiday_name TEXT
)""",
"dim_customer": """CREATE TABLE IF NOT EXISTS dim_customer (
    customer_sk INTEGER PRIMARY KEY, customer_id TEXT NOT NULL UNIQUE, customer_name_masked TEXT NOT NULL,
    gender_code TEXT NOT NULL, birth_date TEXT NOT NULL, cert_type_code TEXT NOT NULL, cert_no_masked TEXT NOT NULL,
    mobile_masked TEXT NOT NULL, customer_level_code TEXT NOT NULL, occupation_code TEXT NOT NULL,
    income_band_code TEXT NOT NULL, marital_status_code TEXT NOT NULL, city_code TEXT NOT NULL,
    province_code TEXT NOT NULL, risk_rating_code TEXT NOT NULL, kyc_level_code TEXT NOT NULL,
    is_staff_flag TEXT NOT NULL, entry_date TEXT NOT NULL, valid_from TEXT NOT NULL,
    valid_to TEXT NOT NULL, is_current_flag TEXT NOT NULL
)""",
"dim_account": """CREATE TABLE IF NOT EXISTS dim_account (
    account_sk INTEGER PRIMARY KEY, account_id TEXT NOT NULL UNIQUE, customer_sk INTEGER NOT NULL,
    account_type_code TEXT NOT NULL, open_date TEXT NOT NULL, close_date TEXT,
    base_currency_code TEXT NOT NULL, statement_day_num INTEGER NOT NULL, payment_due_days INTEGER NOT NULL,
    account_status_code TEXT NOT NULL, valid_from TEXT NOT NULL, valid_to TEXT NOT NULL, is_current_flag TEXT NOT NULL
)""",
"dim_card": """CREATE TABLE IF NOT EXISTS dim_card (
    card_sk INTEGER PRIMARY KEY, card_no_masked TEXT NOT NULL, account_sk INTEGER NOT NULL,
    product_sk INTEGER NOT NULL, card_medium_code TEXT NOT NULL, issued_date TEXT NOT NULL,
    activated_date TEXT, expiry_date TEXT NOT NULL, card_status_code TEXT NOT NULL,
    card_credit_limit REAL, is_primary_card_flag TEXT NOT NULL, primary_card_sk INTEGER,
    valid_from TEXT NOT NULL, valid_to TEXT NOT NULL, is_current_flag TEXT NOT NULL
)""",
"dim_card_product": """CREATE TABLE IF NOT EXISTS dim_card_product (
    product_sk INTEGER PRIMARY KEY, product_id TEXT NOT NULL UNIQUE, product_name TEXT NOT NULL,
    product_level_code TEXT NOT NULL, card_network_code TEXT NOT NULL, annual_fee_amount REAL NOT NULL,
    annual_fee_waiver_rule TEXT, grace_period_days INTEGER NOT NULL, interest_rate_apr REAL NOT NULL,
    min_payment_rate REAL NOT NULL, points_earn_rate REAL NOT NULL, foreign_txn_fee_rate REAL NOT NULL,
    currency_scope_code TEXT NOT NULL, launch_date TEXT NOT NULL, is_active_flag TEXT NOT NULL
)""",
"dim_merchant": """CREATE TABLE IF NOT EXISTS dim_merchant (
    merchant_sk INTEGER PRIMARY KEY, merchant_id TEXT NOT NULL UNIQUE, merchant_name TEXT NOT NULL,
    mcc_code TEXT NOT NULL, mcc_category_desc TEXT NOT NULL, industry_code TEXT NOT NULL,
    city_code TEXT NOT NULL, province_code TEXT NOT NULL, is_online_flag TEXT NOT NULL,
    acquiring_institution_code TEXT NOT NULL
)""",
"dim_transaction_type": """CREATE TABLE IF NOT EXISTS dim_transaction_type (
    txn_type_code TEXT PRIMARY KEY, txn_type_name TEXT NOT NULL, is_consumption_flag TEXT NOT NULL,
    is_financing_flag TEXT NOT NULL, is_fee_flag TEXT NOT NULL, is_interest_flag TEXT NOT NULL,
    is_reversal_type_flag TEXT NOT NULL, earns_points_flag TEXT NOT NULL, is_repayment_flag TEXT NOT NULL
)""",
"dim_channel": """CREATE TABLE IF NOT EXISTS dim_channel (
    channel_code TEXT PRIMARY KEY, channel_name TEXT NOT NULL, channel_group_code TEXT NOT NULL,
    is_ecommerce_flag TEXT NOT NULL
)""",
"dim_currency": """CREATE TABLE IF NOT EXISTS dim_currency (
    currency_code TEXT PRIMARY KEY, currency_name TEXT NOT NULL, currency_numeric_code TEXT NOT NULL,
    decimal_places INTEGER NOT NULL, is_local_currency_flag TEXT NOT NULL
)""",
"dim_status": """CREATE TABLE IF NOT EXISTS dim_status (
    status_code TEXT PRIMARY KEY, status_domain_code TEXT NOT NULL, status_name TEXT NOT NULL,
    is_active_state_flag TEXT NOT NULL, severity_order_num INTEGER NOT NULL
)""",
"fct_transaction": """CREATE TABLE IF NOT EXISTS fct_transaction (
    transaction_id TEXT PRIMARY KEY, txn_timestamp TEXT NOT NULL, date_key INTEGER NOT NULL,
    posting_date_key INTEGER NOT NULL, customer_sk INTEGER NOT NULL, account_sk INTEGER NOT NULL,
    card_sk INTEGER NOT NULL, merchant_sk INTEGER, txn_type_code TEXT NOT NULL, channel_code TEXT NOT NULL,
    currency_code TEXT NOT NULL, auth_code TEXT, txn_amount REAL NOT NULL, txn_amount_cny REAL NOT NULL,
    fx_rate REAL NOT NULL, installment_term_num INTEGER, points_earned INTEGER NOT NULL,
    points_redeemed INTEGER NOT NULL, is_reversal_flag TEXT NOT NULL, original_transaction_id TEXT
)""",
"fct_billing_cycle": """CREATE TABLE IF NOT EXISTS fct_billing_cycle (
    billing_cycle_id TEXT NOT NULL, account_sk INTEGER NOT NULL, statement_date_key INTEGER NOT NULL,
    cycle_start_date_key INTEGER NOT NULL, cycle_end_date_key INTEGER NOT NULL, payment_due_date_key INTEGER NOT NULL,
    currency_code TEXT NOT NULL, beginning_cycle_balance REAL NOT NULL, new_purchase_amount REAL NOT NULL,
    cash_advance_amount REAL NOT NULL, fee_amount REAL NOT NULL, interest_amount REAL NOT NULL,
    total_statement_amount REAL NOT NULL, minimum_payment_amount REAL NOT NULL, closing_cycle_balance REAL NOT NULL,
    points_earned_in_cycle INTEGER NOT NULL, points_expired_in_cycle INTEGER NOT NULL,
    is_past_due_at_billing_flag TEXT NOT NULL, PRIMARY KEY (account_sk, statement_date_key)
)""",
"fct_repayment": """CREATE TABLE IF NOT EXISTS fct_repayment (
    repayment_id TEXT PRIMARY KEY, account_sk INTEGER NOT NULL, date_key INTEGER NOT NULL,
    billing_cycle_id TEXT, channel_code TEXT NOT NULL, currency_code TEXT NOT NULL,
    repayment_amount REAL NOT NULL, principal_portion REAL NOT NULL, interest_portion REAL NOT NULL,
    fee_portion REAL NOT NULL, overpay_portion REAL NOT NULL, points_used_for_offset INTEGER NOT NULL,
    is_on_time_flag TEXT NOT NULL, is_partial_flag TEXT NOT NULL
)""",
"fct_account_monthly_snapshot": """CREATE TABLE IF NOT EXISTS fct_account_monthly_snapshot (
    account_sk INTEGER NOT NULL, month_end_date_key INTEGER NOT NULL, account_status_code TEXT NOT NULL,
    credit_limit REAL NOT NULL, available_credit REAL NOT NULL, outstanding_balance REAL NOT NULL,
    revolving_balance REAL NOT NULL, cash_advance_balance REAL NOT NULL, current_cycle_due_amount REAL NOT NULL,
    past_due_amount REAL NOT NULL, overdue_amount_m1 REAL NOT NULL, overdue_amount_m2 REAL NOT NULL,
    overdue_amount_m3 REAL NOT NULL, overdue_amount_m4p REAL NOT NULL, dpd_days INTEGER NOT NULL,
    overdue_stage_code TEXT NOT NULL, points_balance INTEGER NOT NULL, interest_accrued_mtd REAL NOT NULL,
    fee_charged_mtd REAL NOT NULL, write_off_amount_mtd REAL NOT NULL, is_written_off_flag TEXT NOT NULL,
    active_card_count_in_acct INTEGER NOT NULL, PRIMARY KEY (account_sk, month_end_date_key)
)""",
}


def dkey(d: date) -> int:
    return int(d.strftime("%Y%m%d"))


def iso(d: date) -> str:
    return d.strftime("%Y-%m-%d")


def ts(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def money(x: float) -> float:
    return round(float(x) + 1e-9, 2)


def rand_date(start: date, end: date) -> date:
    if end < start:
        end = start
    return start + timedelta(days=RNG.randint(0, (end - start).days))


def rand_dt(start: date, end: date) -> datetime:
    d = rand_date(start, end)
    return datetime(d.year, d.month, d.day, RNG.randint(0, 23), RNG.randint(0, 59), RNG.randint(0, 59))


def month_end(y: int, m: int) -> date:
    nxt = date(y + 1, 1, 1) if m == 12 else date(y, m + 1, 1)
    return nxt - timedelta(days=1)


def month_ends(start: date, end: date) -> list[date]:
    out = []
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        out.append(month_end(y, m))
        m += 1
        if m > 12:
            m, y = 1, y + 1
    return out


def main() -> None:
    with closing(connect()) as conn:
        with conn:
            conn.execute("PRAGMA foreign_keys = OFF")
            for t in DDL:
                conn.execute(f'DROP TABLE IF EXISTS "{t}"')
            for ddl in DDL.values():
                conn.execute(ddl)

            now = datetime.now().isoformat(timespec="seconds")

            # ---------- 日期维度 ----------
            date_rows = []
            d = START
            while d <= END:
                me = (d + timedelta(days=1)).month != d.month
                qe = me and d.month in (3, 6, 9, 12)
                ye = me and d.month == 12
                fy = d.year if d.month >= 4 else d.year - 1
                fm = ((d.month - 4) % 12) + 1
                mmdd = d.strftime("%m-%d")
                date_rows.append((
                    dkey(d), iso(d), d.year, (d.month - 1) // 3 + 1, d.month,
                    d.strftime("%Y-%m"), d.isocalendar()[1], d.isoweekday(),
                    "Y" if d.weekday() >= 5 else "N", "Y" if me else "N",
                    "Y" if qe else "N", "Y" if ye else "N",
                    fy, fm, (fm - 1) // 3 + 1,
                    "Y" if mmdd in HOLIDAYS else "N", HOLIDAYS.get(mmdd),
                ))
                d += timedelta(days=1)
            conn.executemany("INSERT INTO dim_date VALUES (" + ",".join("?" * 17) + ")", date_rows)

            # ---------- 固定维度 ----------
            conn.executemany(
                "INSERT INTO dim_transaction_type VALUES (?,?,?,?,?,?,?,?,?)",
                [
                    ("PURCH", "消费", "Y", "N", "N", "N", "N", "Y", "N"),
                    ("CASH_ADV", "取现", "N", "Y", "N", "N", "N", "N", "N"),
                    ("REFUND", "退货/冲正", "N", "N", "N", "N", "Y", "N", "N"),
                    ("ANN_FEE", "年费", "N", "N", "Y", "N", "N", "N", "N"),
                    ("FEE_OTHER", "手续费", "N", "N", "Y", "N", "N", "N", "N"),
                    ("INT_CHG", "利息", "N", "N", "N", "Y", "N", "N", "N"),
                    ("INSTALL", "分期", "N", "Y", "N", "N", "N", "Y", "N"),
                    ("PMT_DBIT", "还款借记", "N", "N", "N", "N", "N", "N", "Y"),
                ],
            )
            conn.executemany(
                "INSERT INTO dim_channel VALUES (?,?,?,?)",
                [
                    ("POS", "POS 刷卡", "OFFLINE", "N"),
                    ("ECOM", "电商", "ONLINE", "Y"),
                    ("APP", "手机 App", "ONLINE", "Y"),
                    ("ATM", "ATM", "OFFLINE", "N"),
                    ("COUNTER", "柜面", "OFFLINE", "N"),
                    ("QUICK_PAY", "快捷支付", "ONLINE", "Y"),
                ],
            )
            conn.executemany(
                "INSERT INTO dim_currency VALUES (?,?,?,?,?)",
                [
                    ("CNY", "人民币", "156", 2, "Y"),
                    ("USD", "美元", "840", 2, "N"),
                    ("HKD", "港币", "344", 2, "N"),
                ],
            )
            conn.executemany(
                "INSERT INTO dim_card_product VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                [
                    (1, "P_CLASSIC", "经典普卡", "CLASSIC", "CUP", 0.0, None, 20, 0.1800, 0.1000, 1.0, 0.0150, "SINGLE", "2020-01-01", "Y"),
                    (2, "P_GOLD", "金卡", "GOLD", "CUP", 200.0, "首年免年费", 25, 0.1800, 0.1000, 1.2, 0.0150, "SINGLE", "2020-01-01", "Y"),
                    (3, "P_PLATINUM", "白金卡", "PLATINUM", "VISA", 800.0, "年消费满 10 万免", 30, 0.1800, 0.1000, 1.5, 0.0150, "MULTI", "2021-01-01", "Y"),
                    (4, "P_DIAMOND", "钻石卡", "DIAMOND", "VISA", 2000.0, "年消费满 30 万免", 35, 0.1800, 0.1000, 2.0, 0.0150, "MULTI", "2022-01-01", "Y"),
                ],
            )
            conn.executemany(
                "INSERT INTO dim_status VALUES (?,?,?,?,?)",
                [
                    ("ACCT_ACTIVE", "ACCOUNT", "正常", "Y", 1),
                    ("ACCT_FROZEN", "ACCOUNT", "冻结", "N", 3),
                    ("ACCT_BLOCKED", "ACCOUNT", "止付", "N", 4),
                    ("ACCT_CLOSED", "ACCOUNT", "销户", "N", 5),
                    ("CARD_UNACTIVATED", "CARD", "未激活", "N", 1),
                    ("CARD_ACTIVE", "CARD", "已激活", "Y", 2),
                    ("CARD_LOST", "CARD", "挂失", "N", 4),
                    ("CARD_CANCELLED", "CARD", "注销", "N", 5),
                ],
            )

            # ---------- 商户 ----------
            merchant_rows = []
            for i in range(1, MERCHANT_N + 1):
                mcc, desc = RNG.choice(MCC)
                city, prov = RNG.choice(CITY_PROV)
                online = "Y" if mcc in ("5999", "4511", "5732") else "N"
                merchant_rows.append((
                    i, f"M{i:05d}", f"{desc}商户{i:03d}", mcc, desc, f"IND{mcc[:2]}",
                    city, prov, online, f"ACQ{RNG.randint(1, 30):02d}",
                ))
            conn.executemany("INSERT INTO dim_merchant VALUES (" + ",".join("?" * 10) + ")", merchant_rows)

            # ---------- 客户 ----------
            customer_rows = []
            for sk in range(1, CUSTOMER_N + 1):
                name = RNG.choice(SURNAMES) + "*" + RNG.choice(GIVENS)
                city, prov = RNG.choice(CITY_PROV)
                level = RNG.choices(["NORMAL", "VIP", "SVIP"], [0.8, 0.15, 0.05])[0]
                income = RNG.choice(["B1", "B2", "B3", "B4"])
                entry = rand_date(date(2020, 1, 1), END)
                customer_rows.append((
                    sk, f"C{sk:08d}", name,
                    RNG.choices(["M", "F", "U"], [0.48, 0.48, 0.04])[0],
                    iso(rand_date(date(1960, 1, 1), date(2005, 12, 31))),
                    RNG.choice(["ID_CARD", "PASSPORT"]),
                    f"110101********{RNG.randint(1000, 9999)}",
                    f"1{RNG.randint(30, 89)}****{RNG.randint(1000, 9999)}",
                    level, f"OCC{RNG.randint(1, 10):02d}", income,
                    RNG.choice(["S", "M", "D", "U"]), city, prov,
                    f"R{RNG.randint(1, 5)}", f"L{RNG.randint(1, 3)}",
                    "Y" if RNG.random() < 0.05 else "N", iso(entry),
                    entry.strftime("%Y-%m-%d") + " 00:00:00", "9999-12-31 23:59:59", "Y",
                ))
            conn.executemany("INSERT INTO dim_customer VALUES (" + ",".join("?" * 21) + ")", customer_rows)

            # ---------- 账户 ----------
            cust_pool = list(range(1, CUSTOMER_N + 1)) + [RNG.randint(1, CUSTOMER_N) for _ in range(ACCOUNT_N - CUSTOMER_N)]
            RNG.shuffle(cust_pool)
            account_rows = []
            accounts = []
            for sk in range(1, ACCOUNT_N + 1):
                cust = cust_pool[sk - 1]
                open_d = rand_date(date(2023, 1, 1), date(2026, 10, 31))
                status = RNG.choices(
                    ["ACCT_ACTIVE", "ACCT_FROZEN", "ACCT_BLOCKED", "ACCT_CLOSED"], [0.90, 0.04, 0.03, 0.03]
                )[0]
                close_d = None
                if status == "ACCT_CLOSED":
                    close_d = open_d + timedelta(days=RNG.randint(180, 900))
                    if close_d > END:
                        close_d = END
                base_ccy = RNG.choices(["CNY", "USD", "HKD"], [0.95, 0.03, 0.02])[0]
                account_rows.append((
                    sk, f"A{sk:010d}", cust, RNG.choice(["CC_STD", "CC_BIZ"]),
                    iso(open_d), iso(close_d) if close_d else None, base_ccy,
                    RNG.choice([1, 5, 8, 10, 12, 15, 18, 20, 22, 25, 28]),
                    RNG.randint(18, 26), status,
                    open_d.strftime("%Y-%m-%d") + " 00:00:00", "9999-12-31 23:59:59", "Y",
                ))
                accounts.append({
                    "sk": sk, "customer": cust, "open": open_d, "close": close_d,
                    "ccy": base_ccy, "status": status, "due_days": RNG.randint(18, 26),
                })
            conn.executemany("INSERT INTO dim_account VALUES (" + ",".join("?" * 13) + ")", account_rows)

            # ---------- 卡片 ----------
            acct_pool = list(range(1, ACCOUNT_N + 1)) + [RNG.randint(1, ACCOUNT_N) for _ in range(CARD_N - ACCOUNT_N)]
            RNG.shuffle(acct_pool)
            card_rows = []
            cards_by_account = {}
            primary_by_account = {}
            for sk in range(1, CARD_N + 1):
                acct = acct_pool[sk - 1]
                acc = accounts[acct - 1]
                status = RNG.choices(
                    ["CARD_ACTIVE", "CARD_UNACTIVATED", "CARD_LOST", "CARD_CANCELLED"], [0.85, 0.05, 0.05, 0.05]
                )[0]
                issued = acc["open"] + timedelta(days=RNG.randint(0, 60))
                if issued > END:
                    issued = END
                activated = None
                if status == "CARD_ACTIVE":
                    activated = issued + timedelta(days=RNG.randint(0, 30))
                elif status in ("CARD_LOST", "CARD_CANCELLED"):
                    activated = issued + timedelta(days=RNG.randint(1, 60))
                expiry = month_end(issued.year + 5, issued.month)
                if acct not in primary_by_account:
                    is_primary, primary_sk = "Y", None
                    primary_by_account[acct] = sk
                else:
                    is_primary, primary_sk = "N", primary_by_account[acct]
                limit = money(RNG.uniform(5000, 50000)) if RNG.random() < 0.1 else None
                product = RNG.choice([1, 2, 3, 4])
                card_rows.append((
                    sk, f"6226********{RNG.randint(1000, 9999)}", acct, product,
                    RNG.choices(["PHYSICAL", "VIRTUAL"], [0.9, 0.1])[0],
                    iso(issued), iso(activated) if activated else None, iso(expiry), status, limit,
                    is_primary, primary_sk,
                    issued.strftime("%Y-%m-%d") + " 00:00:00", "9999-12-31 23:59:59", "Y",
                ))
                cards_by_account.setdefault(acct, []).append({"sk": sk, "product": product, "status": status})
            conn.executemany("INSERT INTO dim_card VALUES (" + ",".join("?" * 15) + ")", card_rows)

            # ---------- 交易事实 ----------
            products = {1: 1.0, 2: 1.2, 3: 1.5, 4: 2.0}
            type_weights = [("PURCH", 68), ("CASH_ADV", 5), ("REFUND", 8), ("ANN_FEE", 3),
                            ("FEE_OTHER", 4), ("INT_CHG", 5), ("INSTALL", 4), ("PMT_DBIT", 3)]
            txn_rows = []
            purchases_by_account = {}
            for i in range(1, TXN_N + 1):
                acc = RNG.choice(accounts)
                cards = cards_by_account[acc["sk"]]
                card = RNG.choice(cards)
                ttype = RNG.choices([t for t, w in type_weights], [w for t, w in type_weights])[0]
                if ttype == "REFUND" and not purchases_by_account.get(acc["sk"]):
                    ttype = "PURCH"
                start = max(START, acc["open"])
                end = acc["close"] if acc["close"] and acc["close"] < END else END
                dt = rand_dt(start, end)
                ccy = acc["ccy"] if RNG.random() < 0.95 else RNG.choice(["USD", "HKD"])
                fx = 1.0 if ccy == "CNY" else (RNG.uniform(6.9, 7.3) if ccy == "USD" else RNG.uniform(0.88, 0.92))
                fx = round(fx, 6)
                merchant = None
                auth = None
                term = None
                original = None
                is_rev = "N"
                if ttype == "PURCH":
                    amount = money(min(5000, max(5, RNG.lognormvariate(5.0, 1.0))))
                    merchant = RNG.randint(1, MERCHANT_N)
                    auth = "A" + f"{RNG.randint(0, 99999999):08d}"
                elif ttype == "CASH_ADV":
                    amount = money(RNG.uniform(500, 5000))
                    auth = "A" + f"{RNG.randint(0, 99999999):08d}"
                elif ttype == "REFUND":
                    prior = RNG.choice(purchases_by_account[acc["sk"]])
                    amount = -prior["amount"]
                    original = prior["id"]
                    is_rev = "Y"
                    merchant = prior["merchant"]
                elif ttype == "ANN_FEE":
                    amount = money(max(0.01, RNG.uniform(0, 2000)))
                elif ttype == "FEE_OTHER":
                    amount = money(max(0.01, RNG.uniform(0, 300)))
                elif ttype == "INT_CHG":
                    amount = money(max(0.01, RNG.uniform(0, 1000)))
                elif ttype == "INSTALL":
                    amount = money(RNG.uniform(500, 20000))
                    term = RNG.choice([3, 6, 12, 24])
                    merchant = RNG.randint(1, MERCHANT_N)
                else:  # PMT_DBIT
                    amount = money(RNG.uniform(100, 5000))
                if ttype in ("CASH_ADV",):
                    channel = RNG.choices(["ATM", "COUNTER"], [0.7, 0.3])[0]
                elif ttype in ("ANN_FEE", "FEE_OTHER", "INT_CHG", "PMT_DBIT"):
                    channel = RNG.choice(["COUNTER", "APP"])
                else:
                    channel = RNG.choices(["POS", "ECOM", "APP", "QUICK_PAY"], [0.5, 0.2, 0.2, 0.1])[0]
                points = int(amount * products[card["product"]]) if ttype in ("PURCH", "INSTALL") else 0
                redeemed = int(RNG.uniform(100, 5000)) if RNG.random() < 0.01 else 0
                tid = f"T{i:012d}"
                txn_rows.append((
                    tid, ts(dt), dkey(dt.date()), dkey(dt.date()), acc["customer"], acc["sk"], card["sk"],
                    merchant, ttype, channel, ccy, auth, amount, money(amount * fx), fx,
                    term, max(0, points), redeemed, is_rev, original,
                ))
                if ttype == "PURCH":
                    purchases_by_account.setdefault(acc["sk"], []).append(
                        {"id": tid, "amount": amount, "merchant": merchant}
                    )
            conn.executemany("INSERT INTO fct_transaction VALUES (" + ",".join("?" * 20) + ")", txn_rows)
            # 用 SQLite 自身重算本位币金额，确保与检核口径完全一致（避免 Python/SQLite 舍入边界差异）
            conn.execute("UPDATE fct_transaction SET txn_amount_cny = ROUND(txn_amount * fx_rate, 2)")

            # ---------- 账单事实 ----------
            # 所有合法 (账户, 月末) 组合，保证账单日不早于开户日
            month_pairs = []
            for acc in accounts:
                last = acc["close"] or END
                for e in month_ends(max(START, acc["open"]), last):
                    if acc["open"] <= e <= last:
                        month_pairs.append((acc, e))

            billing_pairs = RNG.sample(month_pairs, BILLING_N)
            by_account = {}
            for acc, e in billing_pairs:
                by_account.setdefault(acc["sk"], []).append((acc, e))

            billing_rows = []
            cycles_by_account = {}
            for acc_sk, items in by_account.items():
                items.sort(key=lambda x: x[1])
                prev = 0.0
                for acc, e in items:
                    new_p = money(RNG.uniform(0, 20000))
                    cash = money(RNG.uniform(0, 5000))
                    fee = money(RNG.uniform(0, 500))
                    interest = money(RNG.uniform(0, 800))
                    total = money(prev + new_p + cash + fee + interest)
                    minimum = money(total * 0.1)
                    due = e + timedelta(days=acc["due_days"])
                    if due > END:
                        due = END
                    start_d = month_end(
                        e.year if e.month > 1 else e.year - 1,
                        e.month - 1 if e.month > 1 else 12,
                    ) + timedelta(days=1)
                    bc_id = f"{acc_sk:05d}-{e.strftime('%Y%m')}"
                    billing_rows.append((
                        bc_id, acc_sk, dkey(e), dkey(start_d), dkey(e), dkey(due), acc["ccy"],
                        money(prev), new_p, cash, fee, interest, total, minimum, total,
                        int(new_p * 1.2), RNG.randint(0, 100),
                        "Y" if RNG.random() < 0.1 else "N",
                    ))
                    cycles_by_account.setdefault(acc_sk, []).append(
                        {"id": bc_id, "due": due, "total": total, "statement": e}
                    )
                    prev = total
            conn.executemany("INSERT INTO fct_billing_cycle VALUES (" + ",".join("?" * 18) + ")", billing_rows)

            # ---------- 还款事实 ----------
            repay_rows = []
            for i in range(1, REPAY_N + 1):
                acc = RNG.choice(accounts)
                cyc = None
                if cycles_by_account.get(acc["sk"]) and RNG.random() < 0.9:
                    cyc = RNG.choice(cycles_by_account[acc["sk"]])
                start = max(START, acc["open"])
                end = acc["close"] if acc["close"] and acc["close"] < END else END
                dt = rand_date(start, end)
                amount = money(RNG.uniform(100, 20000))
                overpay = money(amount * RNG.uniform(0, 0.08))
                fee = money(amount * RNG.uniform(0, 0.03))
                interest = money(amount * RNG.uniform(0, 0.15))
                principal = money(amount - overpay - fee - interest)
                if principal < 0:
                    principal = 0.0
                on_time = "N"
                if cyc:
                    on_time = "Y" if dt <= cyc["due"] else "N"
                repay_rows.append((
                    f"R{i:012d}", acc["sk"], dkey(dt),
                    cyc["id"] if cyc else None,
                    RNG.choice(["COUNTER", "APP", "ATM", "QUICK_PAY"]), acc["ccy"],
                    amount, principal, interest, fee, overpay, 0,
                    on_time, "Y" if RNG.random() < 0.3 else "N",
                ))
            conn.executemany("INSERT INTO fct_repayment VALUES (" + ",".join("?" * 14) + ")", repay_rows)

            # ---------- 账户月末快照 ----------
            active_cards = {}
            for acct, cards in cards_by_account.items():
                active_cards[acct] = sum(1 for c in cards if c["status"] == "CARD_ACTIVE")
            snapshot_pairs = RNG.sample(month_pairs, SNAPSHOT_N)
            snap_rows = []
            for acc, e in snapshot_pairs:
                limit = money(RNG.uniform(10000, 200000))
                outstanding = money(RNG.uniform(0, limit))
                available = money(max(0, limit - outstanding))
                revolving = money(outstanding * RNG.uniform(0, 0.6))
                cash_bal = money(outstanding * RNG.uniform(0, 0.2))
                due = money(outstanding * RNG.uniform(0, 0.5))
                if RNG.random() < 0.2 and outstanding > 0:
                    stage = RNG.choices(["M1", "M2", "M3", "M4+"], [0.5, 0.25, 0.15, 0.1])[0]
                    past = money(outstanding * RNG.uniform(0.05, 0.3))
                    m1 = past if stage == "M1" else 0.0
                    m2 = past if stage == "M2" else 0.0
                    m3 = past if stage == "M3" else 0.0
                    m4 = past if stage == "M4+" else 0.0
                    dpd = {"M1": RNG.randint(1, 30), "M2": RNG.randint(31, 60),
                           "M3": RNG.randint(61, 90), "M4+": RNG.randint(91, 180)}[stage]
                else:
                    stage, past, m1, m2, m3, m4, dpd = "M0", 0.0, 0.0, 0.0, 0.0, 0.0, 0
                write_off = money(RNG.uniform(0, 5000)) if RNG.random() < 0.05 else 0.0
                snap_rows.append((
                    acc["sk"], dkey(e), acc["status"], limit, available, outstanding,
                    revolving, cash_bal, due, past, m1, m2, m3, m4, dpd, stage,
                    RNG.randint(0, 50000), money(RNG.uniform(0, 1000)),
                    money(RNG.uniform(0, 300)), write_off,
                    "Y" if write_off > 0 else "N", active_cards.get(acc["sk"], 0),
                ))
            conn.executemany("INSERT INTO fct_account_monthly_snapshot VALUES (" + ",".join("?" * 22) + ")", snap_rows)

            # ---------- 索引（先建索引，供结欠回填使用） ----------
            for sql in (
                "CREATE INDEX IF NOT EXISTS idx_txn_date ON fct_transaction(date_key)",
                "CREATE INDEX IF NOT EXISTS idx_txn_account ON fct_transaction(account_sk)",
                "CREATE INDEX IF NOT EXISTS idx_txn_card ON fct_transaction(card_sk)",
                "CREATE INDEX IF NOT EXISTS idx_txn_customer ON fct_transaction(customer_sk)",
                "CREATE INDEX IF NOT EXISTS idx_billing_account ON fct_billing_cycle(account_sk)",
                "CREATE INDEX IF NOT EXISTS idx_repay_account ON fct_repayment(account_sk)",
                "CREATE INDEX IF NOT EXISTS idx_repay_cycle ON fct_repayment(billing_cycle_id)",
                "CREATE INDEX IF NOT EXISTS idx_snap_account ON fct_account_monthly_snapshot(account_sk)",
            ):
                conn.execute(sql)

            # ---------- 账单结欠余额回填（= 应还 - 已还本金/费用/利息，可负） ----------
            conn.execute("""
                UPDATE fct_billing_cycle
                SET closing_cycle_balance = ROUND(
                    total_statement_amount - COALESCE((
                        SELECT SUM(repayment_amount - overpay_portion)
                        FROM fct_repayment
                        WHERE fct_repayment.billing_cycle_id = fct_billing_cycle.billing_cycle_id
                    ), 0), 2)
            """)

            # ---------- 语义层 ----------
            counts = write_semantic_layer(conn)

    print("造数完成：")
    print(f"  dim_date={len(date_rows)}  dim_customer={len(customer_rows)}  dim_account={len(account_rows)}  dim_card={len(card_rows)}")
    print(f"  fct_transaction={len(txn_rows)}  fct_billing_cycle={len(billing_rows)}  fct_repayment={len(repay_rows)}  fct_account_monthly_snapshot={len(snap_rows)}")
    print(f"  语义层：tables={counts['tables']} columns={counts['columns']} metrics={counts['metrics']} relations={counts['relations']}")


if __name__ == "__main__":
    main()
