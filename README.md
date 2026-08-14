# DocWise — 智能知识库问答与 Agent 助手平台

> 把任意文档变成「可对话、可溯源、能执行任务」的 AI 助手。
> 本项目是求职用作品：**全链路 RAG（文档解析 → 智能分块 → 混合检索 → Rerank → 流式回答）+ 可量化评测（RAGAS）+ 工具调用 Agent**，并配以完整的工程化（测试 / CI / Docker / 可观测性）。

## ✨ 为什么值得看

| 能力 | 说明 |
|---|---|
| 🎯 全链路 RAG | 不是"调个 API"了事，而是文档 → 分块 → 向量化 → BM25+向量混合检索 → Rerank → 带引用出处的流式回答 |
| 💬 追问改写 | 检测指代不清的追问（"它/这个/上面…"），自动拼接上文改写后再检索 |
| 📊 有评测、有数据 | 32 条测试集 + 10 篇语料：top-1 检索 **纯向量 96.9% → 混合检索 100%**（真实 embedding），生成质量 LLM-as-Judge 忠实度/相关性 **0.99**（DeepSeek 实测）；评测抓到过"引用截断误判"和"Transformer 跨主题漏检"两个真实案例 |
| 🛠 Agent 工具调用 | Function Calling 循环 + 工具注册框架（计算器 / 维基百科搜索），max_turns 防死循环，前端展示调用记录 |
| 🏗 工程化完整 | 70 个单元测试、Ruff 静态检查、检索缓存（跳过重复 embedding）、令牌桶限流、JSON 结构化日志、GitHub Actions CI、Docker 部署 |
| 🖥 全栈可演示 | React 前端流式对话 + Markdown 渲染 + 引用/工具/改写可视化 + 文档分块查看，部署上线有在线 Demo |

## 📈 实测数据（真实 API，2026-08）

| 指标 | 数值 |
|---|---|
| 检索命中率（top-1，52 题 / 20 篇语料） | 纯向量 **96.2%** → 混合检索 **98.1%**（bge-m3 真实嵌入） |
| 生成质量（DeepSeek 判分） | 引用命中 · 忠实度 · 相关性（见 docs/EVAL.md） |
| 单次问答延迟 / 成本 | 约 **1.9~2.3s** / 约 **¥0.0034~0.004**（实测取平均） |
| 评测抓到的真实缺陷 | 引用截断误判（0.25→0.99）、Transformer 跨主题漏检、两题语义陷阱暴露边界 |

详见 [评测体系说明](docs/EVAL.md) 与 `docs/eval/*.json` 报告。

## 🛠 技术栈

- **后端**：Python · FastAPI（异步）· httpx
- **LLM**：OpenAI 兼容接口（可切换 DeepSeek / 通义 / OpenAI）
- **中文分词**：jieba（真实分词，未安装自动回退零依赖方案）
- **向量库**：内存向量存储（MVP）→ FAISS / pgvector / Milvus（演进路径见架构文档）
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

浏览器打开 `http://localhost:5173`，先上传几份文档，然后提问即可。

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
# 访问 http://服务器IP
```

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
