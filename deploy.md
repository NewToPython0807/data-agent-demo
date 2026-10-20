# 云端部署操作记录（T31）

- **目标主机**：腾讯云轻量应用服务器（Ubuntu，登录用户 `ubuntu`）
- **公网 IP**：124.220.154.238
- **登录**：`ssh ubuntu@124.220.154.238`
- **应用**：轻量「智能问数」Data Agent（FastAPI + SQLite，Docker 部署）
- **端口**：8000
- **数据持久化**：`./data:/app/data`
- **配置注入**：`./.env:/app/.env:ro`（直接挂载文件，避免 Docker Compose 对 `$` 做插值）

---

## 0. 前提（重要）

腾讯云控制台 → 轻量应用服务器 → 你的实例 → **防火墙** → 添加规则，放行：

- **TCP 8000**（应用端口）
- TCP 22（SSH）

---

## 1. 登录服务器（本地 PowerShell / 终端）

```powershell
ssh ubuntu@124.220.154.238
```

（Windows 若没 ssh，用完整路径：`C:\Windows\System32\OpenSSH\ssh.exe ubuntu@124.220.154.238`）

---

## 2. 安装 Docker（若镜像已预装则跳过）

```bash
docker --version          # 能打印版本号则跳过下面
curl -fsSL https://get.docker.com | sudo bash -s docker --mirror Aliyun
sudo systemctl enable --now docker
sudo docker --version
```

---

## 3. 上传项目（在**本地**执行）

```powershell
cd "C:\Users\Administrator\Desktop\data agent"
tar -czf deploy.tar.gz app static Dockerfile docker-compose.yml requirements.txt .env .dockerignore
scp deploy.tar.gz ubuntu@124.220.154.238:/home/ubuntu/
```

（Windows scp 完整路径：`C:\Windows\System32\OpenSSH\scp.exe ...`）

---

## 4. 部署启动（在**服务器**上执行，注意 sudo）

```bash
mkdir -p ~/data-agent
tar -xzf ~/deploy.tar.gz -C ~/data-agent
cd ~/data-agent
export PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
sudo -E docker compose up -d --build
```

---

## 5. 验证

```bash
sudo docker compose ps                        # 状态 healthy
curl http://127.0.0.1:8000/api/health         # {"status":"ok",...}
sudo docker compose restart                   # 重启后数据仍在（./data 挂载）
```

本地浏览器打开 **http://124.220.154.238:8000/**，用 `admin` / `test123` 登录。

---

## 6. 常用运维

```bash
cd ~/data-agent
sudo docker compose logs -f        # 看日志
sudo docker compose down           # 停止（数据保留在 ./data）
sudo docker compose up -d          # 再次启动
# 更新代码：重新打包上传覆盖后，再 sudo -E docker compose up -d --build
```

---

## 备注

- 第一版用 **IP 直连（无域名），国内服务器无需备案**。
- 数据在服务器 `~/data-agent/data/agent.db`，请勿误删该目录。
- `deploy.tar.gz` 内含 `.env`（有密钥），部署完可删除：`rm ~/deploy.tar.gz`。
