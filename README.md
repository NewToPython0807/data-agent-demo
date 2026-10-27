# 轻量「智能问数」Data Agent（第三版）

一个部署在云端的轻量数据问答助手：用**中文自然语言**提问，系统先生成**查询计划**与 SQL，**经你审核确认后才执行**，返回查询结果。V3 在 V2 基础上增强了**语义层**、**查询可信度**与**评测反馈**。

## 功能

**问数**
- ✅ 自然语言问数（DeepSeek 生成 SQL）
- ✅ **查询计划展示**：生成 SQL 前展示"分析过程"（指标 / 表 / JOIN / 过滤 / 分组 / 假设 / 歧义）
- ✅ SQL 人工审核：先展示、可手动修改、确认后才执行
- ✅ 只读保护：仅允许 SELECT，写操作直接拦截
- ✅ **超范围拒答**：库里没有的数据直接拒答，不强行生成 SQL
- ✅ **歧义澄清**：问题模糊时先澄清，可"按假设继续"或补充说明
- ✅ **执行失败自动纠错**：把错误反馈给模型，返回修正 SQL 供审核
- ✅ 多轮追问、查询历史
- ✅ **直接执行 SQL（高级）**：不提问也可直接执行只读 SQL

**语义层**
- ✅ 表 / 字段中文名
- ✅ **同义词 / 业务术语**（如"销售额 / 营收 / GMV"）
- ✅ **表关系（JOIN 键）**：多表查询优先使用定义好的关联
- ✅ **业务上下文**：口径说明、注意事项、弃用标记
- ✅ 指标定义（名称 / 口径 / 说明 / 关联表字段 / 单位 / 适用维度），保留变更历史
- ✅ **golden SQL 示例库**：维护"问题 → 正确 SQL"，问数时作为参考

**可信与评测**
- ✅ **结果校验 / 异常提示**：空结果、全 NULL 列、行数过多
- ✅ **结果赞 / 踩**
- ✅ **golden queries 回归**：`python -m app.eval`
- ✅ **统计小卡片**：查询数、赞/踩、赞率、golden 通过率
- ✅ 结果导出 CSV（UTF-8 BOM）

**其它**
- ✅ 网页上传 CSV / Excel（整表覆盖 / 追加）
- ✅ 三段式界面：左导航（数据表 / 指标 / 历史 / 设置）/ 中对话流 / 右结果区
- ✅ 单账号登录（签名 Cookie 会话，7 天）
- ✅ Docker 一键部署，数据持久化

## 技术栈

| 层 | 选型 |
| --- | --- |
| 后端 | Python + FastAPI |
| 数据库 | SQLite（单文件） |
| AI | DeepSeek（OpenAI 兼容接口） |
| 前端 | 原生 HTML / JS（无构建） |
| 部署 | Docker + docker compose |

## 目录结构

```
app/                          后端模块
  main.py                     路由入口
  semantic.py                 语义层（表/字段/同义词/表关系/上下文）
  metrics.py                  指标 CRUD + 变更历史
  prompt.py                   提示词（含查询计划、纠错、golden 示例）
  plan.py                     查询计划解析 / 拒答
  correct.py                  SQL 自动纠错
  golden.py                   golden SQL 示例库
  validate.py                 结果校验
  feedback.py                 赞/踩 + 统计
  eval.py                     golden queries 回归（python -m app.eval）
  llm.py / db.py / auth.py / importer.py / export.py / history.py / upload.py 等
static/                       前端（index.html / login.html / app.js / app.css）
docs/                         V2 / V3 文档（PRD / 开发计划 / 验收清单）
data/                         运行时生成：agent.db、日志（已 gitignore）
deploy.md                     云端部署操作记录
Dockerfile                    镜像定义
docker-compose.yml            编排（数据卷 + .env 挂载）
.env.example                  配置模板
requirements.txt              Python 依赖
seed_data_v2.py               V2 演示造数（regions / customers / products / orders）
seed_credit_card.py           V3 信用卡维度模型造数（14 张表）
seed_credit_card_semantic.py  维度模型 → 语义层落地
seed_check.py                 造数检核（主键/外键/公式/状态）
golden_queries.json           golden 回归用例
credit_card_dimensional_model_v2.md  信用卡维度模型 v2（造数蓝本）
```

---

## 本地开发运行

```powershell
cd "C:\Users\Administrator\Desktop\data agent"

# 1) 准备配置
copy .env.example .env        # 然后编辑 .env 填入密钥等

# 2) 建虚拟环境并装依赖
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 3) 启动
.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

浏览器打开 `http://127.0.0.1:8000/`。首次启动会自动创建语义层/历史/示例库/反馈等内部表（幂等），不影响已有数据。

## 云端部署

见 [deploy.md](./deploy.md)（腾讯云轻量 + Docker + 数据持久化完整步骤）。

---

## 配置说明（.env）

| 键 | 说明 |
| --- | --- |
| `SECRET_KEY` | 会话签名密钥，必填，随机长字符串（`python -c "import secrets;print(secrets.token_hex(32))"`） |
| `ACCOUNT_USERNAME` | 登录账号（默认 admin） |
| `ACCOUNT_PASSWORD_HASH` | 密码的 bcrypt 哈希，用 `python -m app.password_tool 你的密码` 生成 |
| `DEEPSEEK_API_KEY` | DeepSeek API Key（platform.deepseek.com） |
| `DEEPSEEK_BASE_URL` | 默认 `https://api.deepseek.com` |
| `DEEPSEEK_MODEL` | 默认 `deepseek-chat` |
| `DATABASE_PATH` | SQLite 路径，默认 `data/agent.db` |
| `SESSION_MAX_AGE_SECONDS` | 会话有效期，默认 604800（7 天） |
| `MULTI_TURN_CONTEXT_ROUNDS` | 多轮追问上下文轮数，默认 5 |
| `MAX_UPLOAD_MB` | 上传文件上限，默认 50MB |
| `MAX_SQL_CORRECTIONS` | SQL 自动纠错重试次数，默认 2 |

> 忘记密码：重新生成哈希 `python -m app.password_tool 新密码`，替换 `.env` 里的 `ACCOUNT_PASSWORD_HASH` 后重启。

---

## 使用指南（三段式界面）

1. **登录**：打开网页，输入 `.env` 中配置的账号密码。
2. **数据表**：上传 CSV/Excel（覆盖 / 追加）；维护表/字段中文名、**同义词**、**业务上下文**、**弃用标记**，以及**表关系（JOIN 键）**。
3. **指标**：新增/编辑/删除指标（名称、口径、说明、关联表字段、单位、适用维度、同义词），查看变更历史。
4. **问数**：
   - 输入问题 → 对话流展示**分析过程** → 有歧义先澄清 / 超范围直接拒答 → SQL 审核 → 确认执行 → 右侧结果；
   - 执行失败会自动纠错，返回修正 SQL 供再次审核；
   - 底部「直接执行 SQL（高级）」可直接跑只读 SQL。
5. **历史**：查看记录与详情、顶部统计卡片（查询数 / 赞 / 踩 / 赞率 / golden 通过）。
6. **设置**：当前账号、退出登录、**示例库**（问题 → 正确 SQL）。
7. **反馈 / 导出**：结果区 👍 / 👎，以及「导出 CSV」。

## 信用卡维度模型造数（V3）

```powershell
cd "C:\Users\Administrator\Desktop\data agent"
.venv\Scripts\python seed_credit_card.py
.venv\Scripts\python seed_check.py
```

- **维度**：`dim_date`(1461) / `dim_customer`(5000) / `dim_account`(8000) / `dim_card`(12000) / `dim_card_product`(4) / `dim_merchant`(500) / `dim_transaction_type`(8) / `dim_channel`(6) / `dim_currency`(3) / `dim_status`(8)
- **事实**：`fct_transaction`(100000) / `fct_billing_cycle`(50000) / `fct_repayment`(30000) / `fct_account_monthly_snapshot`(40000)
- **语义层**：14 表中文名、189 个字段中文名、16 个指标、26 条表关系
- 固定随机种子，可重复；检核覆盖主键 / 外键 / 日期 / 金额 / 公式 / 逾期 / 冲正 / 主卡 / 语义层

> V2 的演示造数 `seed_data_v2.py` 仍保留（regions / customers / products / orders）。

## golden queries 回归

```powershell
.venv\Scripts\python -m app.eval          # 离线校验 golden SQL 与期望结果
.venv\Scripts\python -m app.eval --llm    # 用 LLM 生成 SQL 再比对（需 API Key）
```

## 常见问题

- **Docker 构建拉不动 `python:3.11-slim`**：给 Docker 配国内镜像加速（见 deploy.md 第 2 步）。
- **Compose 报 `$` 变量警告**：`.env` 里 bcrypt 哈希含 `$`；不影响应用（`.env` 只读挂载、由应用自身解析），可忽略或加 `--env-file /dev/null`。
- **外网打不开 8000**：腾讯云控制台防火墙放行 TCP 8000。
- **登录提示未配置账号**：`.env` 没被读到，确认 `ACCOUNT_USERNAME` 与 `ACCOUNT_PASSWORD_HASH` 已填写并重启。
- **上传 CSV 编码报错**：已自动尝试 UTF-8 / GBK / GB18030 / Big5 / UTF-16；仍失败请将文件另存为 UTF-8（或改用 .xlsx）。
- **追加失败**：需在「目标表」中选择已有表，且文件列需与目标表一致。
- **复杂查询报 `unable to open database file`**：已用 `PRAGMA temp_store = MEMORY` 规避（复杂查询走内存临时表）。
- **问数显示"无法回答"**：说明问题所需数据不在库中/语义层未定义；补充数据或指标后重试。
- **计划 JSON 解析失败**：系统会自动降级为普通 SQL 生成；可重试或换一种问法。
- **自动纠错需要模型**：未配置 `DEEPSEEK_API_KEY` 时不会纠错，直接提示原始错误。

## 文档

- [docs/PRD-v3.md](./docs/PRD-v3.md) — 第三版需求
- [docs/DEVELOPMENT_PLAN-v3.md](./docs/DEVELOPMENT_PLAN-v3.md) — 第三版开发计划
- [docs/验收清单-v3.md](./docs/验收清单-v3.md) — 第三版验收记录
- [credit_card_dimensional_model_v2.md](./credit_card_dimensional_model_v2.md) — 信用卡维度模型 v2（造数蓝本）

## 变更记录

| 版本 | 内容 |
| --- | --- |
| V1 | 自然语言问数、SQL 审核、只读保护、上传、历史、单账号、Docker |
| V2 | 指标/语义层、复杂查询、三段式界面、导出 CSV |
| V3 | 语义层增强（同义词/表关系/业务上下文）、查询计划展示、超范围拒答、歧义澄清、执行失败自动纠错、golden SQL 示例库、结果校验、赞/踩与统计、golden 回归、直接执行 SQL、信用卡维度模型造数 |
