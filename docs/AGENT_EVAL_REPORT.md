# V3 Agent 效果评测报告

> **说明**：本文件是 v1 评测（2026-11-02 15:46，单轮判定口径）的自动产物，其中「准确率 7%」主要受“所有正常问题都被澄清”影响，不能代表模型能力。请以 [AGENT_EVAL_REPORT-v2.md](./AGENT_EVAL_REPORT-v2.md)（双协议、80 条）为准。

- 生成时间：2026-11-02T15:46:08
- 目标服务：http://127.0.0.1:8000
- 测评集：66 条（8 类）

## 一、总体结果

| 指标 | 数值 |
| --- | --- |
| 整体通过率 | 21/66（31.8%） |
| 准确率（正常+空结果） | 7.0% |
| 拒答召回率 | 100.0% |
| 过度拒答率 | 0.0% |
| 澄清命中率 | 90.0% |
| 安全拦截率 | 0.0% |
| 参考 SQL 错误 | 0 条 |

## 二、分类结果

| 类别 | 通过/总数 | 通过率 |
| --- | --- | --- |
| boundary | 9/10 | 90.0% |
| complex | 0/5 | 0.0% |
| empty | 0/3 | 0.0% |
| guard | 0/4 | 0.0% |
| multi_turn | 2/5 | 40.0% |
| normal | 1/25 | 4.0% |
| refusal | 9/9 | 100.0% |
| semantic | 0/5 | 0.0% |

## 三、延迟

| 阶段 | 均值 | P50 | P90 | P95 |
| --- | --- | --- | --- | --- |
| ask（生成计划+SQL） | 2057 ms | 2097 ms | 2616 ms | 2696 ms |
| execute | 54 ms | - | 75 ms | - |
| total P90 | - | - | 2616 ms | - |

## 四、失败案例

| ID | 类别 | 问题 | 期望 | 实际 | 说明 |
| --- | --- | --- | --- | --- | --- |
| N01 | normal | 2025 年消费交易金额是多少 | ok | clarify |  |
| N02 | normal | 2025 年消费交易笔数是多少 | ok | clarify |  |
| N03 | normal | 2025 年活跃卡量是多少 | ok | clarify |  |
| N04 | normal | 2026 年 6 月的消费金额是多少 | ok | clarify |  |
| N05 | normal | 各渠道的消费金额分别是多少 | ok | clarify |  |
| N06 | normal | 各卡产品的消费金额分别是多少 | ok | clarify |  |
| N07 | normal | 消费金额最高的前 5 个商户类别是什么 | ok | clarify |  |
| N08 | normal | 餐饮类商户的消费金额是多少 | ok | clarify |  |
| N09 | normal | 线上渠道的消费金额是多少 | ok | clarify |  |
| N10 | normal | 2025 年取现金额是多少 | ok | clarify |  |
| N11 | normal | 2025 年利息收入是多少 | ok | clarify |  |
| N12 | normal | 2025 年末循环余额是多少 | ok | clarify |  |
| N13 | normal | 2025 年末额度使用率是多少 | ok | clarify |  |
| N14 | normal | 2025 年末逾期率是多少 | ok | clarify |  |
| N15 | normal | 2025 年核销率是多少 | ok | clarify |  |
| N16 | normal | 2025 年积分发放量是多少 | ok | clarify |  |
| N18 | normal | 2025 年末积分负债余额是多少 | ok | clarify |  |
| N19 | normal | 2025 年新增客户数是多少 | ok | clarify |  |
| N20 | normal | 2025 年新增发卡量是多少 | ok | clarify |  |
| N21 | normal | 2025 年还款率是多少 | ok | clarify |  |
| N22 | normal | 2025 年末平均授信额度是多少 | ok | clarify |  |
| N23 | normal | 各客户等级的消费金额分别是多少 | ok | clarify |  |
| N24 | normal | 消费金额最高的账户的消费金额是多少 | ok | clarify |  |
| N25 | normal | 2025 年 12 月的消费金额是多少 | ok | clarify |  |
| B09 | boundary | 重点地区的消费金额是多少 | clarify | refused |  |
| M02 | multi_turn | 只看线上渠道 | ok | clarify |  |
| M04 | multi_turn | 把餐饮去掉 | ok | clarify |  |
| M05 | multi_turn | 其中 VIP 有多少 | ok | clarify |  |
| S01 | semantic | 2025 年交易金额是多少 | ok | clarify |  |
| S02 | semantic | 2025 年末不良率是多少 | ok | clarify |  |

## 五、优化建议

- 准确率偏低：检查提示词中的表/字段说明、JOIN 关系与指标口径；对失败问题补充 golden 示例。
- 只读保护需加强：确保写操作在生成或执行阶段被拦截。
