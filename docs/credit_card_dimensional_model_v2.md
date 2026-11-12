# 信用卡业务 Data Agent 数据方案：维度模型与指标/语义层设计（v2 修订版）

> **修订说明**：本文件基于 `credit_card_dimensional_model.md`（原文件保持不变），按 2026-10-27 评审的 **15 条建议**修订，作为造数与语义层落地的 v2 蓝本。
>
> 设计约定（先读这段再往下看表）：
> 1. 建模方法：Kimball 星型模型。事实表存"业务过程事件"，维度表存"描述性上下文"，指标不落库、由语义层基于事实度量动态计算。
> 2. 键策略：所有维度表用代理键 `*_sk`（BIGINT）做主键，保留自然键（如 `customer_id`）做业务追溯；事实表外键一律引用代理键，`date_key` 采用 `YYYYMMDD` 整数智能键。
> 3. 币种约定：交易保留交易原币金额 + 统一记帐本位币（人民币）金额两个字段，指标层只消费本位币字段；**账单/还款事实表的金额字段一律为本位币（CNY）**，`currency_code` 表示账户本位币。
> 4. 冲正处理：退货/冲正不物理删除原交易，而是新增一条 `is_reversal_flag='Y'` 的负向记录并回指 `original_transaction_id`，指标层用冲正标志过滤。
> 5. 快照可加性：所有余额类度量是 **semi-additive**（跨账户可加、跨时间不可加），指标层对快照类度量只取"期末值"，严禁跨期 SUM。
> 6. 比率指标：一律用 SUM/SUM 重新计算，禁止"对比率求平均"。
> 7. 命名：表名前缀 `dim_`（维度）/ `fct_`（事实），字段 snake_case，注释用中文。

---

## 一、维度表设计（10 张）

### 1.1 dim_date 日期维度

- **粒度**：单日（一行 = 一个自然日）
- **主键**：`date_key`
- **外键**：无

| 字段名 | 数据类型 | 格式约束 | 中文注释 |
|---|---|---|---|
| date_key | INT | YYYYMMDD，如 20261031 | 日期智能键（主键） |
| full_date | DATE | YYYY-MM-DD | 自然日期 |
| year_num | SMALLINT | 1990–2100 | 年份 |
| quarter_num | TINYINT | 1–4 | 季度 |
| month_num | TINYINT | 1–12 | 月份 |
| month_name | VARCHAR(10) | 如 2026-10 | 年月标签 |
| week_of_year_num | TINYINT | 1–53 | 年内周序号 |
| weekday_num | TINYINT | 1=周一 … 7=周日 | 星期序号 |
| is_weekend_flag | CHAR(1) | Y/N | 是否周末 |
| is_month_end_flag | CHAR(1) | Y/N | 是否月末 |
| is_quarter_end_flag | CHAR(1) | Y/N | 是否季末 |
| is_year_end_flag | CHAR(1) | Y/N | 是否年末 |
| fiscal_year_num | SMALLINT | 如 2026 | **财务年（新增）** |
| fiscal_month_num | TINYINT | 1–12 | 财务月（如与自然月错位） |
| fiscal_quarter_num | TINYINT | 1–4 | 财务季度 |
| is_holiday_flag | CHAR(1) | Y/N | 是否法定节假日 |
| holiday_name | VARCHAR(32) | 可空 | 节假日名称 |

### 1.2 dim_customer 客户（持卡人）维度

- **粒度**：单持卡人（一行 = 一个自然人客户，按客户号去重）
- **主键**：`customer_sk`
- **外键**：无（城市/行业等为代码字段，可后续扩展小维度表）

| 字段名 | 数据类型 | 格式约束 | 中文注释 |
|---|---|---|---|
| customer_sk | BIGINT | 代理键 | 客户代理键（主键） |
| customer_id | VARCHAR(32) | 非空唯一 | 客户号（自然键） |
| customer_name_masked | VARCHAR(64) | 脱敏：如 张*三 | 客户姓名（脱敏） |
| gender_code | CHAR(1) | M/F/U | 性别代码 |
| birth_date | DATE | YYYY-MM-DD | 出生日期 |
| cert_type_code | VARCHAR(4) | 如 ID_CARD/PASSPORT | 证件类型代码 |
| cert_no_masked | VARCHAR(32) | 脱敏：保留前4后3 | 证件号码（脱敏） |
| mobile_masked | VARCHAR(20) | 脱敏：138****1234 | 手机号（脱敏） |
| customer_level_code | VARCHAR(8) | 如 VIP/NORMAL | 客户等级 |
| occupation_code | VARCHAR(8) | 参照行标代码表 | 职业代码 |
| income_band_code | VARCHAR(8) | 如 B1(0-10万)/B2/B3 | 收入区间代码 |
| marital_status_code | CHAR(1) | S/M/D/U | 婚姻状况 |
| city_code | VARCHAR(8) | 行政区划代码 | 常驻城市代码 |
| province_code | VARCHAR(8) | 行政区划代码 | 省份代码 |
| risk_rating_code | VARCHAR(4) | 如 R1–R5 | 客户风险等级 |
| kyc_level_code | VARCHAR(4) | 如 L1/L2/L3 | KYC 核验等级 |
| is_staff_flag | CHAR(1) | Y/N | 是否本行员工 |
| entry_date | DATE | YYYY-MM-DD | 客户建档日期 |
| valid_from | TIMESTAMP | YYYY-MM-DD HH:MI:SS | SCD2 生效时间 |
| valid_to | TIMESTAMP | 同上，9999-12-31 表示当前 | SCD2 失效时间 |
| is_current_flag | CHAR(1) | Y/N | SCD2 当前有效标志 |

### 1.3 dim_account 账户维度

- **粒度**：单信用卡账户（一行 = 一个信用账户；一人可有多账户）
- **主键**：`account_sk`
- **外键**：`customer_sk` → dim_customer；`currency_code` → dim_currency；`account_status_code` → dim_status

| 字段名 | 数据类型 | 格式约束 | 中文注释 |
|---|---|---|---|
| account_sk | BIGINT | 代理键 | 账户代理键（主键） |
| account_id | VARCHAR(32) | 非空唯一 | 信用账户号（自然键） |
| customer_sk | BIGINT | FK | 客户代理键 |
| account_type_code | VARCHAR(8) | 如 CC_STD/CC_BIZ | 账户类型（个人/公务卡等） |
| open_date | DATE | YYYY-MM-DD | 账户开户日期 |
| close_date | DATE | 可空 | 账户销户日期 |
| base_currency_code | CHAR(3) | ISO 4217，默认 CNY | 账户主币种 |
| statement_day_num | TINYINT | **1–31**（月末按当月最后一天处理） | 账单日出帐日 |
| payment_due_days | TINYINT | 通常 18–26 | 免息还款期天数 |
| account_status_code | VARCHAR(8) | FK dim_status | 账户当前状态（正常/冻结/止付/销户） |
| valid_from | TIMESTAMP | SCD2 | SCD2 生效时间 |
| valid_to | TIMESTAMP | SCD2 | SCD2 失效时间 |
| is_current_flag | CHAR(1) | Y/N | SCD2 当前有效标志 |

> 说明：**授信额度不放维度表**——额度会调整，放月度快照事实表（fct_account_monthly_snapshot）才能追溯历史。

### 1.4 dim_card 卡片维度

- **粒度**：单张卡（一行 = 一个卡号；含实体卡与虚拟卡）
- **主键**：`card_sk`
- **外键**：`account_sk` → dim_account；`product_sk` → dim_card_product；`card_status_code` → dim_status

| 字段名 | 数据类型 | 格式约束 | 中文注释 |
|---|---|---|---|
| card_sk | BIGINT | 代理键 | 卡片代理键（主键） |
| card_no_masked | VARCHAR(24) | 脱敏：6226********1234 | 卡号（脱敏自然键） |
| account_sk | BIGINT | FK | 所属信用账户 |
| product_sk | BIGINT | FK | 卡产品代理键 |
| card_medium_code | VARCHAR(8) | PHYSICAL/VIRTUAL | 卡介质（实体/虚拟） |
| issued_date | DATE | YYYY-MM-DD | 制卡日期 |
| activated_date | DATE | 可空 | 激活日期 |
| expiry_date | DATE | 格式化为月末日 | 卡片有效期 |
| card_status_code | VARCHAR(8) | FK dim_status | 卡片状态（未激活/激活/挂失/注销） |
| card_credit_limit | DECIMAL(18,2) | ≥0，可空 | 卡片级子额度（可覆盖账户额度，空则共用账户额度） |
| is_primary_card_flag | CHAR(1) | Y/N | 是否主卡（副卡=N） |
| primary_card_sk | BIGINT | 可空，FK 本表 | 副卡关联的主卡（自引用） |
| valid_from | TIMESTAMP | YYYY-MM-DD HH:MI:SS | **SCD2 生效时间（新增）** |
| valid_to | TIMESTAMP | 同上，9999-12-31 表示当前 | **SCD2 失效时间（新增）** |
| is_current_flag | CHAR(1) | Y/N | **SCD2 当前有效标志（新增）** |

### 1.5 dim_card_product 卡产品维度

- **粒度**：单个卡产品（一行 = 一个产品 SKU）
- **主键**：`product_sk`
- **外键**：无

| 字段名 | 数据类型 | 格式约束 | 中文注释 |
|---|---|---|---|
| product_sk | BIGINT | 代理键 | 产品代理键（主键） |
| product_id | VARCHAR(32) | 非空唯一 | 产品代码（自然键） |
| product_name | VARCHAR(64) | 非空 | 产品名称 |
| product_level_code | VARCHAR(8) | CLASSIC/GOLD/PLATINUM/DIAMOND | 产品等级（普卡/金卡/白金/钻石） |
| card_network_code | VARCHAR(8) | CUP/VISA/MC/AMEX/JCB | 卡组织/清算网络 |
| annual_fee_amount | DECIMAL(18,2) | ≥0 | 年费标准金额（元） |
| annual_fee_waiver_rule | VARCHAR(255) | 可空 | 年费减免规则描述 |
| grace_period_days | TINYINT | 通常 18–56 | 免息期天数上限 |
| interest_rate_apr | DECIMAL(6,4) | 如 0.1800 表示 18.00% APR | 循环利息年化利率 |
| min_payment_rate | DECIMAL(6,4) | 如 0.1000 表示 10% | 最低还款比例 |
| points_earn_rate | DECIMAL(8,4) | 如 1.0000 = 1 元 1 分 | 消费积分累计比例（元:分） |
| foreign_txn_fee_rate | DECIMAL(6,4) | 如 0.0150 | 货币转换费率 |
| currency_scope_code | VARCHAR(8) | SINGLE/MULTI | 支持单币种/多币种标识 |
| launch_date | DATE | YYYY-MM-DD | 产品上线日期 |
| is_active_flag | CHAR(1) | Y/N | 产品是否在售 |

### 1.6 dim_merchant 商户维度

- **粒度**：单个受理商户（一行 = 一个商户号）
- **主键**：`merchant_sk`
- **外键**：无

| 字段名 | 数据类型 | 格式约束 | 中文注释 |
|---|---|---|---|
| merchant_sk | BIGINT | 代理键 | 商户代理键（主键） |
| merchant_id | VARCHAR(32) | 非空唯一 | 商户编号（自然键） |
| merchant_name | VARCHAR(128) | 非空 | 商户名称 |
| mcc_code | CHAR(4) | 0000–9999 | 商户类别码 MCC |
| mcc_category_desc | VARCHAR(64) | 如 餐饮/百货/航空 | MCC 大类描述 |
| industry_code | VARCHAR(8) | 行业分类代码 | 所属行业代码 |
| city_code | VARCHAR(8) | 行政区划代码 | 商户所在城市 |
| province_code | VARCHAR(8) | 行政区划代码 | 商户所在省份 |
| is_online_flag | CHAR(1) | Y/N | 是否线上商户 |
| acquiring_institution_code | VARCHAR(16) | 收单机构代码 | 收单机构 |

### 1.7 dim_transaction_type 交易类型维度

- **粒度**：单个交易类型（一行 = 一个交易类型码）
- **主键**：`txn_type_code`
- **外键**：无

| 字段名 | 数据类型 | 格式约束 | 中文注释 |
|---|---|---|---|
| txn_type_code | VARCHAR(8) | 如 PURCH/CASH_ADV/REFUND/ANN_FEE/INT_CHG/PMT_DBIT | 交易类型代码（主键） |
| txn_type_name | VARCHAR(32) | 非空 | 交易类型名称（消费/取现/退货/年费/利息/还款借记等） |
| is_consumption_flag | CHAR(1) | Y/N | 是否计入消费口径（统计"交易金额"时的过滤开关） |
| is_financing_flag | CHAR(1) | Y/N | 是否融资类交易（取现/分期） |
| is_fee_flag | CHAR(1) | Y/N | 是否费用类 |
| is_interest_flag | CHAR(1) | Y/N | 是否利息类 |
| is_reversal_type_flag | CHAR(1) | Y/N | 是否冲正/退货类交易 |
| earns_points_flag | CHAR(1) | Y/N | 是否累计积分 |
| is_repayment_flag | CHAR(1) | Y/N | 是否还款入账类 |

> 设计意图：这一组 Y/N 旗标就是**指标口径的开关**——语义层定义"交易金额"时写 `WHERE is_consumption_flag='Y' AND is_reversal_type_flag='N'`，口径变更只需改维表旗标 + 重算，不改指标定义。

### 1.8 dim_channel 渠道维度

- **粒度**：单个交易渠道（一行 = 一个渠道码）
- **主键**：`channel_code`
- **外键**：无

| 字段名 | 数据类型 | 格式约束 | 中文注释 |
|---|---|---|---|
| channel_code | VARCHAR(8) | 如 POS/ECOM/APP/ATM/COUNTER/QUICK_PAY | 渠道代码（主键） |
| channel_name | VARCHAR(32) | 非空 | 渠道名称 |
| channel_group_code | VARCHAR(8) | ONLINE/OFFLINE | 渠道大类（线上/线下） |
| is_ecommerce_flag | CHAR(1) | Y/N | 是否电子商务渠道 |

### 1.9 dim_currency 币种维度

- **粒度**：单个币种（一行 = 一个 ISO 4217 币种）
- **主键**：`currency_code`
- **外键**：无

| 字段名 | 数据类型 | 格式约束 | 中文注释 |
|---|---|---|---|
| currency_code | CHAR(3) | ISO 4217，如 CNY/USD/HKD | 币种代码（主键） |
| currency_name | VARCHAR(32) | 非空 | 币种名称 |
| currency_numeric_code | CHAR(3) | ISO 数字码，如 156 | 币种数字代码 |
| decimal_places | TINYINT | 通常 2 | 小数位数 |
| is_local_currency_flag | CHAR(1) | Y/N | 是否本位币 |

### 1.10 dim_status 状态维度（账户/卡片共用）

- **粒度**：单个状态码（一行 = 一个状态）
- **主键**：`status_code`（**全局唯一，建议加域前缀**，如 `ACCT_ACTIVE` / `CARD_ACTIVE`）
- **外键**：无

| 字段名 | 数据类型 | 格式约束 | 中文注释 |
|---|---|---|---|
| status_code | VARCHAR(16) | 全局唯一，域前缀 + 状态 | 状态代码（主键） |
| status_domain_code | VARCHAR(8) | ACCOUNT/CARD | 状态所属域 |
| status_name | VARCHAR(32) | 非空 | 状态名称（正常/冻结/止付/销户等） |
| is_active_state_flag | CHAR(1) | Y/N | 是否"可用/健康"状态 |
| severity_order_num | TINYINT | 1–99 | 风险严重程度排序（用于取"最严重状态"） |

> 修订说明：原设计为复合主键 `(status_domain_code, status_code)`，但事实表只存 `status_code`，FK 无法指向复合主键。现改为 **`status_code` 全局唯一（域前缀）**，事实表 FK 可直接引用。

---

## 二、事实表设计（4 张）

### 2.1 fct_transaction 交易事实表

- **业务粒度**：单笔交易/授权记录（一行 = 一笔交易，含消费、取现、退货冲正、费用、利息计提入账）
- **主键**：`transaction_id`
- **外键**：date_key、customer_sk、account_sk、card_sk、merchant_sk、txn_type_code、channel_code、currency_code

| 字段名 | 数据类型 | 格式约束 | 中文注释 | 度量可加性 |
|---|---|---|---|---|
| transaction_id | VARCHAR(64) | 全局唯一，主键 | 交易流水号 | — |
| txn_timestamp | TIMESTAMP | YYYY-MM-DD HH:MI:SS.fff | 交易时间戳（退化维度） | — |
| date_key | INT | FK dim_date | 交易日期键 | — |
| posting_date_key | INT | FK dim_date | 入账日期键 | — |
| customer_sk | BIGINT | FK | 客户 | — |
| account_sk | BIGINT | FK | 账户 | — |
| card_sk | BIGINT | FK | 卡片 | — |
| merchant_sk | BIGINT | FK，可空（如年费无商户） | 商户 | — |
| txn_type_code | VARCHAR(8) | FK | 交易类型 | — |
| channel_code | VARCHAR(8) | FK | 渠道 | — |
| currency_code | CHAR(3) | FK | 交易币种（原币） | — |
| auth_code | VARCHAR(32) | 可空 | 授权码 | — |
| txn_amount | DECIMAL(18,2) | **非冲正 >0；冲正类 <0** | 交易原币金额 | **additive** |
| txn_amount_cny | DECIMAL(18,2) | 同上符号规则 | 交易本位币金额（指标层唯一消费口径） | **additive** |
| fx_rate | DECIMAL(12,6) | >0 | 交易汇率（原币→CNY） | **non-additive** |
| installment_term_num | TINYINT | 可空，1–60 | 分期期数（非分期为空） | — |
| points_earned | INT | ≥0 | 本笔累计积分 | **additive** |
| points_redeemed | BIGINT | ≥0 | 本笔兑换/抵扣积分（兑换交易才有） | **additive** |
| is_reversal_flag | CHAR(1) | Y/N | 是否冲正/退货记录 | — |
| original_transaction_id | VARCHAR(64) | 可空，FK 本表 | 冲正关联的原交易流水号（自引用） | — |

### 2.2 fct_billing_cycle 账单事实表

- **业务粒度**：单账户 × 单个账单周期（一行 = 一个账户的一期账单）
- **主键**：(`account_sk`, `statement_date_key`) 复合主键（辅以 `billing_cycle_id` 业务键）
- **外键**：account_sk、statement_date_key、payment_due_date_key、currency_code

| 字段名 | 数据类型 | 格式约束 | 中文注释 | 度量可加性 |
|---|---|---|---|---|
| billing_cycle_id | VARCHAR(32) | 唯一，如 账户号+期号 | 账单周期业务键 | — |
| account_sk | BIGINT | FK，主键之一 | 账户 | — |
| statement_date_key | INT | FK dim_date，主键之一 | 账单日 | — |
| cycle_start_date_key | INT | FK dim_date | 账单周期起日 | — |
| cycle_end_date_key | INT | FK dim_date | 账单周期止日 | — |
| payment_due_date_key | INT | FK dim_date | 到期还款日 | — |
| currency_code | CHAR(3) | FK | 账单币种（= 账户本位币 CNY） | — |
| beginning_cycle_balance | DECIMAL(18,2) | **可为负（溢缴/贷记）** | 上期结转余额 | **semi-additive**（跨时间不可加） |
| new_purchase_amount | DECIMAL(18,2) | ≥0 | 本期新增消费金额 | **additive** |
| cash_advance_amount | DECIMAL(18,2) | ≥0 | 本期取现金额 | **additive** |
| fee_amount | DECIMAL(18,2) | ≥0 | 本期费用金额（年费/手续费等） | **additive** |
| interest_amount | DECIMAL(18,2) | ≥0 | 本期计收利息金额 | **additive** |
| total_statement_amount | DECIMAL(18,2) | **= beginning + new_purchase + cash_advance + fee + interest**（还款在 fct_repayment 体现，不在此扣减） | 本期应还总额 | **additive** |
| minimum_payment_amount | DECIMAL(18,2) | ≥0 | 本期最低还款额 | **additive** |
| closing_cycle_balance | DECIMAL(18,2) | **可为负（溢缴/贷记）** | 本期账单结欠余额 | **semi-additive** |
| points_earned_in_cycle | INT | ≥0 | 本期账单确认累计积分 | **additive** |
| points_expired_in_cycle | INT | ≥0 | 本期失效积分 | **additive** |
| is_past_due_at_billing_flag | CHAR(1) | Y/N | 出账时是否已逾期 | — |

> 修订说明：`total_statement_amount` 明确为"上期结转 + 本期消费 + 取现 + 费用 + 利息"的**毛额**，不扣减还款；还款对账单的冲抵关系由 `fct_repayment.billing_cycle_id` 关联分析。

### 2.3 fct_repayment 还款事实表

- **业务粒度**：单笔还款入账记录（一行 = 一笔还款）
- **主键**：`repayment_id`
- **外键**：account_sk、date_key、channel_code、currency_code；`billing_cycle_id` 为**业务关联字段（非 FK）**，指向 `fct_billing_cycle.billing_cycle_id`

| 字段名 | 数据类型 | 格式约束 | 中文注释 | 度量可加性 |
|---|---|---|---|---|
| repayment_id | VARCHAR(64) | 全局唯一，主键 | 还款流水号 | — |
| account_sk | BIGINT | FK | 账户 | — |
| date_key | INT | FK dim_date | 还款入账日期键 | — |
| billing_cycle_id | VARCHAR(32) | 可空，业务关联（非 FK） | 冲抵的账单周期 | — |
| channel_code | VARCHAR(8) | FK | 还款渠道 | — |
| currency_code | CHAR(3) | FK | 还款币种（= 账户本位币 CNY） | — |
| repayment_amount | DECIMAL(18,2) | >0（本位币） | 还款总金额 | **additive** |
| principal_portion | DECIMAL(18,2) | ≥0 | 还款冲抵本金部分 | **additive** |
| interest_portion | DECIMAL(18,2) | ≥0 | 还款冲抵利息部分 | **additive** |
| fee_portion | DECIMAL(18,2) | ≥0 | 还款冲抵费用部分 | **additive** |
| overpay_portion | DECIMAL(18,2) | ≥0 | 溢缴部分 | **additive** |
| points_used_for_offset | BIGINT | ≥0 | 积分抵扣还款使用的积分数 | **additive** |
| is_on_time_flag | CHAR(1) | Y/N | 是否到期日前入账 | — |
| is_partial_flag | CHAR(1) | Y/N | 是否部分还款（未还清账单） | — |

> 修订说明：`billing_cycle_id` 是 fact → fact 的业务关联，**不建 FK 约束**；如需严格星型，可增加 `dim_billing_cycle` 维度。

### 2.4 fct_account_monthly_snapshot 账户月末快照事实表

- **业务粒度**：每账户 × 每自然月月末（一行 = 一个账户一个月末时点状态）
- **主键**：(`account_sk`, `month_end_date_key`) 复合主键
- **外键**：account_sk、month_end_date_key、account_status_code → dim_status

| 字段名 | 数据类型 | 格式约束 | 中文注释 | 度量可加性 |
|---|---|---|---|---|
| account_sk | BIGINT | FK，主键之一 | 账户 | — |
| month_end_date_key | INT | FK dim_date，主键之一 | 月末日期键 | — |
| account_status_code | VARCHAR(8) | FK dim_status | 月末账户状态 | — |
| credit_limit | DECIMAL(18,2) | ≥0 | 月末授信总额度 | **semi-additive** |
| available_credit | DECIMAL(18,2) | ≥0 | 月末可用额度 | **semi-additive** |
| outstanding_balance | DECIMAL(18,2) | ≥0 | 月末未偿余额 | **semi-additive** |
| revolving_balance | DECIMAL(18,2) | ≥0 | 月末循环余额（出账后未全额还清部分） | **semi-additive** |
| cash_advance_balance | DECIMAL(18,2) | ≥0 | 月末取现未还余额 | **semi-additive** |
| current_cycle_due_amount | DECIMAL(18,2) | ≥0 | 当期应还金额 | **semi-additive** |
| past_due_amount | DECIMAL(18,2) | ≥0 | 月末逾期金额（已过到期还款日的欠款） | **semi-additive** |
| overdue_amount_m1 | DECIMAL(18,2) | ≥0 | 逾期 1–30 天余额 | **semi-additive** |
| overdue_amount_m2 | DECIMAL(18,2) | ≥0 | 逾期 31–60 天余额 | **semi-additive** |
| overdue_amount_m3 | DECIMAL(18,2) | ≥0 | 逾期 61–90 天余额 | **semi-additive** |
| overdue_amount_m4p | DECIMAL(18,2) | ≥0 | 逾期 90 天以上余额 | **semi-additive** |
| dpd_days | INT | ≥0 | 月末逾期天数（非逾期=0） | **non-additive** |
| overdue_stage_code | VARCHAR(4) | M0/M1/M2/M3/M4+ | 月末逾期阶段 | **non-additive** |
| points_balance | BIGINT | ≥0 | 月末积分余额 | **semi-additive** |
| interest_accrued_mtd | DECIMAL(18,2) | ≥0 | 本月累计计收利息（**仅趋势/余额参考，不参与 interest_income**） | **additive** |
| fee_charged_mtd | DECIMAL(18,2) | ≥0 | 本月累计费用 | **additive** |
| write_off_amount_mtd | DECIMAL(18,2) | ≥0 | 本月核销金额 | **additive** |
| is_written_off_flag | CHAR(1) | Y/N | 本月是否发生核销 | — |
| active_card_count_in_acct | TINYINT | ≥0 | 该账户月末活跃卡张数 | **semi-additive** |

> 修订说明：`interest_accrued_mtd` 与 `fct_billing_cycle.interest_amount` 存在口径重叠，**利息收入指标以账单表为准**，快照表该字段仅作余额/趋势参考。

---

## 三、指标 / 语义层定义（12 个核心 + 4 个扩展）

通用约定：
- 比率类指标一律 **SUM/SUM 派生**，标注为 non-additive（跨维度不可先算再求和，必须重算）。
- 快照类指标默认取 **统计周期末快照值**，跨时间不可加。
- 时间参数 `{{ period }}` 由语义层注入（日/月/季/年）。

### 3.1 核心指标（12 个）

| 指标名 (snake_case) | 中文名称 | 业务定义 | 聚合粒度 | 可加性 | 计算逻辑（引用度量 + 聚合方式） | 数值格式 |
|---|---|---|---|---|---|---|
| txn_amount_total | 消费交易金额 | 统计周期内信用卡消费交易的本位币金额合计（剔除冲正） | 交易 | additive | `SUM(fct_transaction.txn_amount_cny)`，过滤 `dim_transaction_type.is_consumption_flag='Y' AND fct_transaction.is_reversal_flag='N'` | DECIMAL(18,2)，金额/元 |
| txn_count | 消费交易笔数 | 统计周期内消费交易的笔数合计（剔除冲正） | 交易 | additive | `COUNT(fct_transaction.transaction_id)`，过滤条件同上 | BIGINT，整数 |
| active_card_count | 活跃卡量 | 统计周期内至少发生 1 笔消费交易的卡数量 | 卡 × 统计周期 | non-additive（去重计数，跨期不可加总） | `COUNT(DISTINCT fct_transaction.card_sk)`，过滤条件同 txn_amount_total | INT，整数 |
| credit_utilization_rate | 额度使用率 | 期末未偿余额占授信额度的比率，衡量额度占用水平 | 账户月末快照 | non-additive（比率） | `SUM(fct_account_monthly_snapshot.outstanding_balance) / SUM(fct_account_monthly_snapshot.credit_limit)`，取周期末月快照 | DECIMAL(7,4)，百分比 |
| revolving_balance_total | 循环余额 | 期末客户出账后未全额还清、进入循环计息的余额合计 | 账户月末快照 | semi-additive（跨账户可加，跨时间取期末值不累加） | `SUM(fct_account_monthly_snapshot.revolving_balance)`，取周期末快照 | DECIMAL(18,2)，金额/元 |
| interest_income | 利息收入 | 统计周期内向客户计收的循环/取现利息收入合计 | 账单周期 | additive | `SUM(fct_billing_cycle.interest_amount)`（**以账单表为准**；快照表 interest_accrued_mtd 不参与） | DECIMAL(18,2)，金额/元 |
| repayment_rate | 还款率 | 到期账单金额中实际收回的比例，衡量还款行为健康度 | 账单周期 | non-additive（比率） | `SUM(fct_repayment.repayment_amount - fct_repayment.overpay_portion) / SUM(fct_billing_cycle.total_statement_amount)`，按 `billing_cycle_id` 关联匹配 | DECIMAL(7,4)，百分比 |
| overdue_rate | 逾期率（余额口径） | 期末逾期金额占未偿余额的比例；亦可派生账户数口径（`逾期账户数/有余额账户数`） | 账户月末快照 | non-additive（比率） | `SUM(fct_account_monthly_snapshot.past_due_amount) / SUM(fct_account_monthly_snapshot.outstanding_balance)`，取周期末快照 | DECIMAL(7,4)，百分比 |
| write_off_rate | 核销率 | 周期内核销金额占平均未偿余额的比例，反映终极损失 | 账户月末快照 | non-additive（比率） | `SUM(fct_account_monthly_snapshot.write_off_amount_mtd) / AVG(fct_account_monthly_snapshot.outstanding_balance)`（**分母 = 周期内各月末未偿余额的平均；单月时等于月末值**） | DECIMAL(7,4)，百分比 |
| points_issued | 积分发放量 | 统计周期内向客户累计发放的积分总量 | 交易 / 账单周期 | additive | `SUM(fct_transaction.points_earned)`（交易级）；对账口径用 `SUM(fct_billing_cycle.points_earned_in_cycle)` | BIGINT，整数 |
| points_redeemed | 积分兑换量 | 统计周期内客户兑换/抵扣使用的积分总量 | 交易 | additive | `SUM(fct_transaction.points_redeemed)` | BIGINT，整数 |
| points_liability_balance | 积分负债余额 | 期末尚未兑换的积分余额，财务上构成预计负债 | 账户月末快照 | semi-additive（跨账户可加，跨时间取期末值） | `SUM(fct_account_monthly_snapshot.points_balance)`，取周期末快照 | BIGINT，整数 |

### 3.2 扩展指标（4 个，可选）

| 指标名 (snake_case) | 中文名称 | 业务定义 | 计算逻辑 | 可加性 |
|---|---|---|---|---|
| new_customer_count | 新增客户数 | 统计周期内新建档客户数 | `COUNT(DISTINCT dim_customer.customer_sk)`，过滤 `entry_date` 在周期内 | additive |
| new_card_count | 新增发卡量 | 统计周期内新发卡数量 | `COUNT(dim_card.card_sk)`，过滤 `issued_date` 在周期内 | additive |
| activation_rate | 激活率 | 已激活卡数 / 已发卡数 | `SUM(CASE WHEN activated_date IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*)`（按发卡周期） | non-additive |
| avg_credit_limit | 平均授信额度 | 期末账户平均授信额度 | `AVG(fct_account_monthly_snapshot.credit_limit)`，取周期末快照 | non-additive |

派生指标扩展建议：
- `avg_txn_amount_per_card`（卡均交易金额）= txn_amount_total / active_card_count，non-additive
- `net_points_flow`（净积分流量）= points_issued − points_redeemed，additive
- `overdue_rate_by_account_count`（户逾期率）= `COUNT(快照表 dpd_days>0) / COUNT(快照行)`，non-additive

---

## 四、指标/语义层落地示例（dbt MetricFlow YAML 风格，仅示意格式）

以消费交易语义模型与两个指标为例：

```yaml
semantic_models:
  - name: fct_transaction
    description: "信用卡交易事实表（单笔交易粒度）"
    model: ref('fct_transaction')
    primary_entity: transaction

    dimensions:
      - name: txn_timestamp
        type: time
        type_params:
          grain: day
      - name: is_reversal_flag
        type: categorical

    measures:
      - name: txn_amount_cny
        agg: sum
        create_metric: false
      - name: transaction_count
        expr: transaction_id
        agg: count
        create_metric: false

metrics:
  - name: txn_amount_total          # 消费交易金额
    description: "统计周期内消费交易本位币金额合计，剔除冲正"
    type: simple
    type_params:
      measure: txn_amount_cny
    filter: |
      "{{ SemanticModel.dim_transaction_type.is_consumption_flag }}" = 'Y'
      and is_reversal_flag = 'N'

  - name: credit_utilization_rate   # 额度使用率（派生比率）
    description: "期末未偿余额 / 授信额度，SUM/SUM 派生"
    type: derived
    type_params:
      expr: outstanding_balance_sum / credit_limit_sum
```

---

## 五、关键设计决策说明（评审要点）

| # | 决策 | 理由 |
|---|---|---|
| 1 | 额度放快照事实表而非维度表 | 额度随时间调整，需追溯历史值；维度表只放"缓慢变化"的描述属性 |
| 2 | 交易类型维度的旗标开关（is_consumption_flag 等） | 指标口径集中在维度旗标中管理，口径变更不改指标代码 |
| 3 | 冲正用负向记录 + 自引用，不删原交易 | 保留完整审计链，指标用旗标过滤 |
| 4 | 比率指标全部 SUM/SUM 派生 | 避免"平均的比率"统计陷阱 |
| 5 | 余额类度量统一 semi-additive 标注 | 防止语义层跨时间对余额求和（最常见的口径事故） |
| 6 | 逾期分级（M1–M4+）在快照表预置金额桶 | 催收与减值口径（账龄分析）可直接下钻，无需逐期重算 |
| 7 | 积分在交易、账单、快照三层都有度量 | 交易层（明细对账）、账单层（出账确认）、快照层（负债余额）各有消费方，不冗余 |
| 8 | 币种双字段（原币 + 本位币） | 指标层只消费本位币，多币种明细保留在事实层可审计 |
| 9 | `dim_status` 主键改为 `status_code` 全局唯一（域前缀） | 解决事实表单列 FK 无法指向复合主键的问题 |
| 10 | `dim_card` 增加 SCD2 | 卡片状态会变化，需还原历史时点状态 |
| 11 | 账单/还款金额统一为本位币（CNY） | 与交易表"原币+本位币"分工明确，避免多币种口径混乱 |
| 12 | `total_statement_amount` 明确为毛额公式 | 口径可复现；还款冲抵单独在 fct_repayment 分析 |
| 13 | `fct_repayment.billing_cycle_id` 仅作业务关联（非 FK） | 避免 fact → fact 的建模歧义；如需严格星型可加 dim_billing_cycle |
| 14 | 余额字段允许为负（溢缴/贷记） | 与真实业务一致，避免校验误判 |
| 15 | 补充"维度初始值 + SQLite 映射" | 保证造数确定、可复现、可直接落地 |

---

## 六、维度初始值（造数用）

> 以下为建议初始值，可在造数时按需调整；行数为固定维度表。

### 6.1 dim_date
- 范围：`2023-01-01` ~ `2026-12-31`（4 年，约 1461 行）
- 衍生字段：年/季/月/周/星期/周末/月末/季末/年末/财务年/财务月/财务季/节假日

### 6.2 dim_transaction_type（8 行）

| txn_type_code | txn_type_name | is_consumption | is_financing | is_fee | is_interest | is_reversal | earns_points | is_repayment |
|---|---|---|---|---|---|---|---|---|
| PURCH | 消费 | Y | N | N | N | N | Y | N |
| CASH_ADV | 取现 | N | Y | N | N | N | N | N |
| REFUND | 退货/冲正 | N | N | N | N | Y | N | N |
| ANN_FEE | 年费 | N | N | Y | N | N | N | N |
| FEE_OTHER | 手续费 | N | N | Y | N | N | N | N |
| INT_CHG | 利息 | N | N | N | Y | N | N | N |
| INSTALL | 分期 | N | Y | N | N | N | Y | N |
| PMT_DBIT | 还款借记 | N | N | N | N | N | N | Y |

### 6.3 dim_channel（6 行）

| channel_code | channel_name | channel_group_code | is_ecommerce_flag |
|---|---|---|---|
| POS | POS 刷卡 | OFFLINE | N |
| ECOM | 电商 | ONLINE | Y |
| APP | 手机 App | ONLINE | Y |
| ATM | ATM | OFFLINE | N |
| COUNTER | 柜面 | OFFLINE | N |
| QUICK_PAY | 快捷支付 | ONLINE | Y |

### 6.4 dim_currency（3 行）

| currency_code | currency_name | currency_numeric_code | decimal_places | is_local_currency_flag |
|---|---|---|---|---|
| CNY | 人民币 | 156 | 2 | Y |
| USD | 美元 | 840 | 2 | N |
| HKD | 港币 | 344 | 2 | N |

### 6.5 dim_card_product（4 行）

| product_id | product_name | product_level_code | card_network_code | annual_fee_amount | grace_period_days | interest_rate_apr | min_payment_rate | points_earn_rate |
|---|---|---|---|---|---|---|---|---|
| P_CLASSIC | 经典普卡 | CLASSIC | CUP | 0.00 | 20 | 0.1800 | 0.1000 | 1.0000 |
| P_GOLD | 金卡 | GOLD | CUP | 200.00 | 25 | 0.1800 | 0.1000 | 1.2000 |
| P_PLATINUM | 白金卡 | PLATINUM | VISA | 800.00 | 30 | 0.1800 | 0.1000 | 1.5000 |
| P_DIAMOND | 钻石卡 | DIAMOND | VISA | 2000.00 | 35 | 0.1800 | 0.1000 | 2.0000 |

### 6.6 dim_status（8 行）

| status_code | status_domain_code | status_name | is_active_state_flag | severity_order_num |
|---|---|---|---|---|
| ACCT_ACTIVE | ACCOUNT | 正常 | Y | 1 |
| ACCT_FROZEN | ACCOUNT | 冻结 | N | 3 |
| ACCT_BLOCKED | ACCOUNT | 止付 | N | 4 |
| ACCT_CLOSED | ACCOUNT | 销户 | N | 5 |
| CARD_UNACTIVATED | CARD | 未激活 | N | 1 |
| CARD_ACTIVE | CARD | 已激活 | Y | 2 |
| CARD_LOST | CARD | 挂失 | N | 4 |
| CARD_CANCELLED | CARD | 注销 | N | 5 |

### 6.7 dim_merchant（示例 10 行）

| merchant_id | merchant_name | mcc_code | mcc_category_desc | is_online_flag |
|---|---|---|---|---|
| M0001 | 某某餐饮 | 5812 | 餐饮 | N |
| M0002 | 某某超市 | 5411 | 超市 | N |
| M0003 | 某某百货 | 5311 | 百货 | N |
| M0004 | 某某航空 | 4511 | 航空 | Y |
| M0005 | 某某酒店 | 7011 | 酒店 | N |
| M0006 | 某某电商 | 5999 | 零售 | Y |
| M0007 | 某某交通 | 4111 | 交通 | N |
| M0008 | 某某医院 | 8011 | 医疗 | N |
| M0009 | 某某数码 | 5732 | 电子 | Y |
| M0010 | 某某加油站 | 5541 | 加油 | N |

### 6.8 客户 / 账户 / 卡片（生成规则，非固定行）
- `dim_customer`：按客户号去重；姓名/证件/手机脱敏；性别/年龄/城市/等级/风险等级随机但可复现（固定随机种子）。
- `dim_account`：每人 1–2 个账户；开户日期在 2023–2026；状态以正常为主。
- `dim_card`：每账户 1–3 张卡；含实体卡/虚拟卡；主卡/副卡关系；状态以已激活为主。

---

## 七、SQLite 落地映射（造数脚本用）

| 模型类型 | SQLite 建议类型 | 说明 |
|---|---|---|
| BIGINT / INT / SMALLINT / TINYINT | INTEGER | SQLite 统一为 INTEGER |
| DECIMAL(18,2) / DECIMAL(7,4) | REAL | 金额/比率用 REAL，展示时格式化 |
| DATE | TEXT | `YYYY-MM-DD` |
| TIMESTAMP | TEXT | `YYYY-MM-DD HH:MM:SS` |
| CHAR/VARCHAR | TEXT | 不强制长度 |
| 复合主键 | `PRIMARY KEY (a, b)` | 如 fct_billing_cycle、fct_account_monthly_snapshot |
| 外键 | `FOREIGN KEY` 可声明 | SQLite 默认不强制；造数时按顺序插入 |
| 索引 | 事实表 FK、日期键建索引 | 提升查询性能 |

---

## 八、造数规模建议（待确认）

| 表 | 建议行数 | 说明 |
|---|---|---|
| dim_date | ~1461 | 2023-01-01 ~ 2026-12-31 |
| dim_customer | 5,000 | 客户 |
| dim_account | 8,000 | 人均 1–2 账户 |
| dim_card | 12,000 | 每账户 1–3 张 |
| dim_card_product | 4 | 固定 |
| dim_merchant | 500 | 可扩展 |
| dim_transaction_type | 8 | 固定 |
| dim_channel | 6 | 固定 |
| dim_currency | 3 | 固定 |
| dim_status | 8 | 固定 |
| fct_transaction | 100,000 | 单笔交易 |
| fct_billing_cycle | 50,000 | 账户 × 期数 |
| fct_repayment | 30,000 | 还款记录 |
| fct_account_monthly_snapshot | 40,000 | 账户 × 月末 |

> 实际行数由用户确认后调整；以上为默认建议。

---

## 九、变更记录

| 版本 | 日期 | 内容 |
|---|---|---|
| v2 | 2026-10-27 | 基于评审 15 条建议修订：状态维主键、卡片 SCD2、账单公式、币种口径、余额可负、账单日 1–31、指标口径澄清、扩展指标、维度初始值、SQLite 映射、财务年 |
