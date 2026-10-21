# 轻量「智能问数」Data Agent（第二版）

一个部署在云端的轻量数据问答助手：用**中文自然语言**提问，系统先生成 SQL，**经你审核确认后才执行**，返回查询结果。支持**指标/语义层**、**复杂查询（多表关联 / 聚合后筛选 / 窗口函数）**、**三段式界面**与**结果导出 CSV**。

## 功能

- ✅ 自然语言问数（DeepSeek 生成 SQL）
- ✅ SQL 人工审核：先展示、可手动修改、确认后才执行
- ✅ 只读保护：仅允许 SELECT，写操作直接拦截
- ✅ **指标 / 语义层**：表与字段中文名、指标口径（含单位、适用维度），保留变更历史
- ✅ **复杂查询**：多表 JOIN、HAVING、窗口函数（10 万行以内）
- ✅ **三段式界面**：左导航（数据表 / 指标 / 历史 / 设置）/ 中对话流 / 右结果区
- ✅ **结果导出 CSV**（UTF-8 BOM，Excel 直接打开）
- ✅ 网页上传 CSV / Excel（整表覆盖 / 追加）
- ✅ 查询历史、多轮追问
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
app/                后端（FastAPI 路由与业务模块）
static/             前端（index.html / login.html / app.js / app.css）
docs/               第二版文档（PRD-v2 / 开发计划 / 验收清单 / 技术决策记录）
data/               运行时生成：agent.db、日志（已 gitignore）
deploy.md           云端部署操作记录
Dockerfile          镜像定义
docker-compose.yml  编排（数据卷 + .env 挂载）
.env.example        配置模板
requirements.txt    Python 依赖
seed_data_v2.py     测试造数脚本（可重复运行）
test_*.py           功能/回归测试脚本
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

浏览器打开 `http://127.0.0.1:8000/`。首次启动会自动创建语义层四张表（幂等），不影响已有数据。

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

> 忘记密码：重新生成哈希 `python -m app.password_tool 新密码`，替换 `.env` 里的 `ACCOUNT_PASSWORD_HASH` 后重启。

---

## 使用指南（三段式界面）

1. **登录**：打开网页，输入 `.env` 中配置的账号密码。
2. **数据表**（左侧「数据表」）：上传 CSV/Excel（覆盖 / 追加，追加需选目标表）；编辑表与字段中文名。
3. **指标**（左侧「指标」）：新增/编辑/删除指标（名称、口径、说明、关联表字段、单位、适用维度）；查看变更历史。
4. **问数**（点左上角「智能问数」）：输入中文问题 → 中间对话流出现 SQL → 可编辑 → 点「确认执行」→ 右侧显示结果；可继续追问。
5. **历史**（左侧「历史」）：查看历史记录与详情，支持刷新/清空。
6. **设置**（左侧「设置」）：查看当前账号、退出登录。
7. **导出**：执行查询后点结果区「导出 CSV」。

## 测试造数

```powershell
.venv\Scripts\python seed_data_v2.py
```

生成 4 张关联表：`regions`(5) / `customers`(1万) / `products`(500) / `orders`(10万)，含中文、空值、边界值与关联键；可重复运行（整表替换）。

## 测试脚本

| 脚本 | 覆盖 |
| --- | --- |
| `test_semantic_v2.py` | 表/字段中文名、指标 CRUD、变更历史 |
| `test_prompt_v2.py` | 提示词注入语义层 |
| `test_complex_v2.py` | 复杂查询提示策略 |
| `test_metric_question_v2.py` | 指标问数快路径 |
| `test_complex_query_v2.py` | JOIN / HAVING / 窗口函数执行 |
| `test_export_v2.py` / `test_t27_export.py` | CSV 导出 |
| `test_t25_complex.py` | 10 万行复杂查询 |
| `test_t26_ui.py` / `test_ui_bindings_v2.py` | 前端完整性静态检查 |
| `test_t28_regression.py` | V1 功能回归 |

## 常见问题

- **Docker 构建拉不动 `python:3.11-slim`**：给 Docker 配国内镜像加速（见 deploy.md 第 2 步）。
- **Compose 报 `$` 变量警告**：`.env` 里 bcrypt 哈希含 `$`；本项目已用"挂载 .env 文件"方式规避，警告可忽略。
- **外网打不开 8000**：腾讯云控制台防火墙放行 TCP 8000。
- **登录提示未配置账号**：`.env` 没被读到，确认 `ACCOUNT_USERNAME` 与 `ACCOUNT_PASSWORD_HASH` 已填写并重启。
- **上传 CSV 编码报错**：已自动尝试 UTF-8 / GBK / GB18030 / Big5 / UTF-16；仍失败请将文件另存为 UTF-8（或改用 .xlsx）。
- **追加失败**：需在「目标表」中选择已有表，且文件列需与目标表一致。
- **复杂查询报 `unable to open database file`**：已用 `PRAGMA temp_store = MEMORY` 规避（复杂查询走内存临时表）。
