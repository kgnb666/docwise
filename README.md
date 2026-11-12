# DocWise — 智能知识库问答与 Agent 助手平台

![CI](https://github.com/kgnb666/docwise/actions/workflows/ci.yml/badge.svg)

> 把任意文档变成「可对话、可溯源、能执行任务」的 AI 助手。
> DocWise 提供文档解析、混合检索、带引用的流式问答、离线评测和 Agent 工具调用。

[在线入口](https://docwise.myiskg.com/)需要管理员开通账号。

## ✨ 为什么值得看

| 能力 | 说明 |
|---|---|
| 🎯 全链路 RAG | 不是"调个 API"了事，而是文档 → 分块 → 向量化 → BM25+向量混合检索 → Rerank → 带引用出处的流式回答（支持 txt / md / pdf / **docx**） |
| 💬 追问改写 | 检测指代不清的追问（"它/这个/上面…"），自动拼接上文改写后再检索 |
| 🧠 知识库外问题兜底 | 双模式：strict（只答知识库，防幻觉）/ chat（未命中时用常识回答或联网查证），靠相关度阈值自动分流（实测 0.4 分开无关/相关） |
| 📊 有评测、有数据 | 52 条测试集 + 20 篇语料：top-1 检索 **纯向量 96.2% → 混合检索 98.1%**（真实 embedding），生成质量 LLM-as-Judge 忠实度 **0.99**/相关性 **0.95**（DeepSeek 实测）；评测抓到过"引用截断误判"和"Transformer 跨主题漏检"等真实案例 |
| 🛠 Agent 工具调用 | Function Calling 循环 + 工具注册框架（计算器 / 维基百科搜索），max_turns 防死循环，前端展示调用记录 |
| 🔐 私有知识库 | 管理员开通账号。文档、检索索引、缓存和浏览器聊天历史按账号隔离，退出或切换账号时同步关闭其他标签页的旧工作区 |
| 💾 文档持久化 | 快照写入成功后更新索引。删除失败时保留原文档，成功删除后重启不会恢复，并发检索不会把已删片段写回缓存 |
| 🏗 工程化 | 145 项后端测试、21 项前端测试、Ruff / ESLint、检索缓存、令牌桶限流、结构化日志、GitHub Actions 和 Docker Compose |
| 🖥 浏览器工作区 | React 流式问答、Markdown、引用和文档分块查看 |

## 📈 实测数据（真实 API，2026-08）

| 指标 | 数值 |
|---|---|
| 检索命中率（top-1，52 题 / 20 篇语料） | 纯向量 **96.2%** → 混合检索 **98.1%**（bge-m3 真实嵌入） |
| 生成质量（DeepSeek 判分） | 引用命中 · 忠实度 · 相关性（见 docs/EVAL.md） |
| 单次问答延迟 / 成本 | 约 **1.9s**（3 条样本平均） / 约 **¥0.0037**（按字符数估算 token） |
| 评测抓到的真实缺陷 | 引用截断误判（0.25→0.99）、Transformer 跨主题漏检、两题语义陷阱暴露边界 |

详见 [评测体系说明](docs/EVAL.md) 与 `docs/eval/*.json` 报告。

## 🛠 技术栈

- **后端**：Python · FastAPI（异步）· httpx
- **LLM**：OpenAI 兼容接口（可切换 DeepSeek / 通义 / OpenAI）
- **中文分词**：jieba（真实分词，未安装自动回退零依赖方案）
- **存储**：SQLite 账号和会话，按账号保存的 JSON 快照与内存向量索引
- **检索**：自研轻量 BM25 + 向量余弦 + Rerank 混合检索
- **前端**：React · Vite · TypeScript（Markdown 渲染 + 引用展开查看）
- **部署**：Docker Compose（生产 nginx）· 云服务器

## 🚀 快速开始（本地开发）

> 建议 Python 3.11 ~ 3.13（3.14 在向量化阶段可能遇到部分包的预编译 wheel 缺失问题）

### 后端

```bash
# Windows
powershell -ExecutionPolicy Bypass -File scripts/setup.ps1

# macOS / Linux
bash scripts/setup.sh
```

或者手动：

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # 填入你的 LLM API Key
python scripts/manage_accounts.py add alice
uvicorn app.main:app --reload --port 8000
```

> **没有 API Key 也能体验检索流程**：把 `.env` 里的 `EMBEDDING_PROVIDER` 改为 `hash`，
> 系统会用内置的离线哈希嵌入跑通「上传 → 分块 → 检索」全链路（生成环节需要 Key）。

### 前端

```bash
cd frontend
npm install
npm run dev        # 打开 http://localhost:5173
```

浏览器打开 `http://localhost:5173`，用刚创建的账号登录，再上传文档和提问。
每个账号有自己的文档、检索索引和浏览器会话历史。批量导入时指定账号：

```bash
cd backend
python scripts/import_kb.py --account alice ../my-notes
```

### 冒烟测试

```bash
cd backend && python -m pytest -v
```

### 离线检索评测（无需 API Key）

```bash
cd backend && python scripts/run_eval.py
# 输出「纯向量 vs 混合 vs 混合+Rerank」命中率对比报告 → docs/eval/offline_report.json
```

### 真实评测与基准（需要 API Key）

```bash
cd backend
python scripts/run_eval.py --embedding openai --tokenizer jieba --reranker-api --top-k 1
python scripts/run_eval_quality.py      # recall / 忠实度 / 相关性 → docs/eval/quality_report.json
python scripts/benchmark.py             # 延迟与成本实测 → docs/eval/benchmark.json
```

### 生成质量评测（LLM-as-Judge，需要 API Key）

```bash
cd backend && python scripts/run_eval_quality.py
# 输出 recall / 忠实度 / 相关性报告 → docs/eval/quality_report.json
```

## 📁 目录结构

```
├── backend/            # FastAPI 后端
│   ├── app/
│   │   ├── api/        # HTTP 接口层（文档 / 聊天 / 评测）
│   │   ├── rag/        # RAG 核心（分块 / 嵌入 / 检索 / 流水线）
│   │   ├── storage/    # 向量存储抽象
│   │   ├── agent/      # Agent 工具框架（阶段 2）
│   │   └── eval/       # RAGAS 评测（阶段 2）
│   └── tests/          # 单元测试
├── frontend/           # React + Vite 前端
├── docs/
│   ├── ARCHITECTURE.md # 架构图与演进路线
│   └── ROADMAP.md      # 12 周开发路线图
└── scripts/            # 环境安装脚本
```

## 🚀 部署上线（生产模式）

```bash
cp backend/.env.example backend/.env   # 填 API Key
docker compose up --build -d            # 前端 nginx(80) → /api 反代 → 后端
docker compose exec backend python scripts/manage_accounts.py add alice
# 通过 HTTPS 域名登录
```

升级旧版时，请按[部署指南](docs/DEPLOYMENT.md#3-一键启动)在维护窗口内为旧快照指定归属。
旧版未分配归属的文档与浏览器会话保留在原存储中。

详见 [部署指南](docs/DEPLOYMENT.md)（VPS 选购 / Docker 安装 / HTTPS / 排查）。

## 📖 更多文档

- [项目完成报告](docs/FINAL_REPORT.md)
- [架构设计](docs/ARCHITECTURE.md)
- [评测体系说明](docs/EVAL.md)
- [12 周路线图](docs/ROADMAP.md)
- [投递前检查清单](docs/CHECKLIST.md)
- [面试题库（24 问含答案）](docs/INTERVIEW.md)
- [3 分钟演示脚本](docs/DEMO_SCRIPT.md)
- [简历条目模板](docs/RESUME.md)

## 📜 License

MIT
