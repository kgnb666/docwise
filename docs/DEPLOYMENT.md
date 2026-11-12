# 部署上线指南（给零基础）

先在本机验证文档上传和问答，再按需部署到可通过 HTTPS 访问的服务器。

## 方案 A：本地部署（无 Docker、不花钱，推荐先做这个）

生产构建 + 预览，效果等同于线上（静态资源 + API 同源代理）：

```bash
# 1) 构建前端（输出到 frontend/dist）
cd frontend && npm run build

# 2) 终端 1：在 backend 目录创建账号并启动后端
.\.venv\Scripts\python scripts/manage_accounts.py add alice
.\.venv\Scripts\uvicorn app.main:app --host 127.0.0.1 --port 8000

# 3) 终端 2：启动前端生产预览（/api 自动代理到 8000）
cd frontend && npm run preview -- --port 4173

# 浏览器打开 http://localhost:4173
```

- 在 `http://localhost:4173` 登录刚创建的账号，确认能上传文件并在文档列表查看分块。
- 局域网多人访问时，请通过 HTTPS 反向代理提供前端入口。

## 方案 B：云服务器上线（推荐投递前再做）

> 成本：国内轻量云服务器约 ¥30-60/月（新用户常有一折活动），最低配 2C2G 足够。

### 0. 准备工作

- [ ] 本机安装 **Git**（https://git-scm.com/download/win）
- [ ] 注册 GitHub 账号，把项目推到仓库（见文末"推送项目"）
- [ ] 购买云服务器（阿里云/腾讯云轻量应用服务器，选 Ubuntu 22.04）
- [ ] 安全组放行 **80 端口**（HTTPS 时还要 443）

### 1. 服务器装 Docker

SSH 登录服务器（Windows 用 PowerShell 或 FinalShell）：

```bash
# Ubuntu 一键安装 Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER   # 当前用户免 sudo 用 docker
# 退出重新登录后验证：
docker --version
```

## 2. 拉取代码并配置

```bash
git clone https://github.com/<你的用户名>/docwise.git
cd docwise/backend
cp .env.example .env
nano .env    # 填入 OPENAI_API_KEY（DeepSeek/通义都行，改 base_url 和 model）
```

## 3. 一键启动

```bash
cd ~/docwise
docker compose up --build -d
docker compose ps          # 两个容器都 running 即成功
docker compose exec backend python scripts/manage_accounts.py add alice
```

`/api/health` 可用于检查服务存活。浏览器登录请使用下节配置的 HTTPS 域名，
并保持 `AUTH_COOKIE_SECURE=true`。账号由运维通过上面的命令创建，密码在终端交互输入。

升级前备份 `backend/data`。旧版 `data/documents` 里的快照没有归属信息。
确认整批文档属于同一账号后，在后端停止期间执行一次性归属迁移：

```bash
docker compose stop backend
docker compose run --rm --no-deps backend python scripts/manage_accounts.py adopt-legacy alice
docker compose up -d backend
```

命令保留源快照。中断后可用原账号继续，完成后重跑会跳过已完成的迁移。
如旧文档分别属于不同人，可让各账号重新上传自己的原文档。新增批量导入使用
`python scripts/import_kb.py --account alice <目录>`，导入后重启正在运行的后端。

## 4. 配置 HTTPS

用 Caddy 比 Nginx+certbot 简单得多。在服务器上：

```bash
sudo apt install caddy
# 编辑 /etc/caddy/Caddyfile：
#   docwise.example.com {
#       reverse_proxy localhost:80
#   }
sudo systemctl reload caddy
```

把域名解析到服务器 IP，Caddy 自动签发 Let's Encrypt 证书。

本机非 HTTPS 开发环境可在后端配置 `AUTH_COOKIE_SECURE=false`，公网保持 HTTPS。

## 5. 常见问题排查

| 现象 | 原因与解决 |
|---|---|
| 页面打不开 | `docker compose ps` 看容器状态；`docker compose logs frontend` 看日志；安全组是否放行 80 |
| 上传成功但问答报"生成失败" | 后端 .env 的 Key 没填对；`docker compose logs backend` 看具体错误 |
| 回答不流式、一坨一坨出 | nginx 缓冲没关——检查 frontend/nginx.conf 的 `proxy_buffering off` |
| 改完代码不生效 | `docker compose up --build -d` 重新构建镜像 |
| 停机维护 | `docker compose down`；重启 `docker compose up -d` |

## 6. 运维小贴士

- 日志：`docker compose logs -f backend`
- 更新：`git pull && docker compose up --build -d`
- 备份：目前向量数据在内存（容器重启即清），上线前请换持久化存储
  （pgvector/Milvus + data volume），这是路线图里"演进"的一部分

---

## 附：把项目推到 GitHub（本机）

```bash
cd 项目目录
git init
git add .
git commit -m "feat: DocWise RAG + Agent 知识库问答平台"
git branch -M main
git remote add origin https://github.com/<你的用户名>/docwise.git
git push -u origin main
```

推送后 GitHub Actions 会自动跑 CI（pytest + 前端构建），
README 顶部加个状态徽章（Actions 页面里复制 badge 代码），简历里放仓库链接。
