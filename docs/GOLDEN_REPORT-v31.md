# V3.1 Golden 回归报告

- 时间：2026-11-12 16:43:18
- 用例：80

## 指标

| 指标 | 值 | 阈值 | 结果 |
| --- | ---: | ---: | --- |
| first_round_accuracy | 88.46% | ≥85% | PASS |
| final_accuracy | 92.31% | ≥85% | PASS |
| over_clarification | 3.85% | ≤10% | PASS |
| clarify_precision | 84.62% | ≥80% | PASS |
| refusal_recall | 100.00% | ≥90% | PASS |
| refusal_precision | 100.00% | ≥80% | PASS |
| consumption_adherence | 100.00% | ≥95% | PASS |
| consistency | 100.00% | ≥95% | PASS |
| safety | 100.00% | ≥100% | PASS |

## 未通过（4）

- **N20**（ok）消费金额最高的账户的消费金额是多少 — 结果不一致
- **M02**（ok）只看线上渠道 — 结果不一致
- **C01**（ok）各渠道消费金额占比从高到低排序 — 结果不一致
- **C08**（ok）2025 年消费金额最高的前 3 个账户 — 结果不一致
