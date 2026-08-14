# 部署上线指南（给零基础）

> 目标：让项目有一个**可访问的在线地址**（面试官点开就能玩）。预计 1-2 小时。
> 成本：国内轻量云服务器约 ¥30-60/月（新用户常有一折活动），最低配 2C2G 足够。

## 0. 准备工作

- [ ] 本机安装 **Git**（https://git-scm.com/download/win）
- [ ] 注册 GitHub 账号，把项目推到仓库（见文末"推送项目"）
- [ ] 购买云服务器（阿里云/腾讯云轻量应用服务器，选 Ubuntu 22.04）
- [ ] 安全组放行 **80 端口**（HTTPS 时还要 443）

## 1. 服务器装 Docker

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
```

浏览器访问 `http://<服务器公网IP>` —— 应该能看到 DocWise 界面。

## 4. 配置 HTTPS（强烈建议，面试官更信任 https）

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

> 没有域名？先裸 IP 跑着演示也行，简历里写"部署于 xxx.xx.xx.xx"，
> 正式投递前再补域名。

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
