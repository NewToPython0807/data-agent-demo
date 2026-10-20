# 轻量「智能问数」Data Agent

一个部署在云端的轻量数据问答助手：用**中文自然语言**提问，系统先生成 SQL，**经你审核确认后才执行**，返回查询结果。原始数据可通过网页上传 CSV/Excel 随时更新。

## 功能

- ✅ 自然语言问数（DeepSeek 生成 SQL）
- ✅ SQL 人工审核：先展示、可手动修改、确认后才执行
- ✅ 只读保护：仅允许 SELECT，写操作直接拦截
- ✅ 网页上传 CSV / Excel（整表覆盖 / 追加）
- ✅ 表结构展示、查询历史、多轮追问
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
static/             前端页面（index.html / login.html / app.js）
data/               运行时生成：agent.db、日志（已 gitignore）
deploy.md           云端部署操作记录
Dockerfile          镜像定义
docker-compose.yml  编排（数据卷 + .env 挂载）
.env.example        配置模板
requirements.txt    Python 依赖
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

浏览器打开 `http://127.0.0.1:8000/`。

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

## 使用指南

1. **登录**：打开网页，输入 `.env` 中配置的账号密码。
2. **问数**：输入中文问题 → 点"生成 SQL" → 页面展示 SQL（可编辑）→ 点"确认执行" → 查看结果表格。
3. **追问**：直接继续提问（如"再按地区分组"），系统会结合最近 5 轮上下文理解。
4. **上传数据**：选择 CSV/Excel → 选"整表覆盖 / 追加" → 点"上传"；表名取文件名。
5. **查看表结构 / 历史**：点页面顶部对应按钮。

## 常见问题

- **Docker 构建拉不动 `python:3.11-slim`**：给 Docker 配国内镜像加速（见 deploy.md 第 2 步）。
- **Compose 报 `$` 变量警告**：`.env` 里 bcrypt 哈希含 `$`，本项目已用"挂载 .env 文件"方式规避，警告可忽略。
- **外网打不开 8000**：腾讯云控制台防火墙放行 TCP 8000。
- **登录提示未配置账号**：`.env` 没被读到，确认 `ACCOUNT_USERNAME` 与 `ACCOUNT_PASSWORD_HASH` 已填写并重启。
