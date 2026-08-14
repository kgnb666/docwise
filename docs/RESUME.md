# 简历条目（写实版，直接可用）

> 原则：只写真实存在的能力；需要真实数据的地方标注 [待补]，拿到 Key 后填上。
> 数字比形容词有说服力：70 个测试、10 篇语料、32 条测试集、5 轮工具上限、20QPM 限流……

## 中文版

**DocWise — 带评测体系的 RAG + Agent 知识库问答平台** ｜ 独立开发 ｜ 2025.XX – 至今

- 独立实现全链路 RAG 系统：文档解析（txt/md/pdf）→ 标题感知分块（800 字符/100 重叠）→ 向量化 → **BM25+向量混合检索** → Rerank 精排 → SSE 流式回答，回答带引用出处且可点击溯源；
- 自建 32 条 QA 测试集与评测体系：四档检索配置（纯向量/混合/混合+OverlapRerank/混合+bge-reranker API）命中率对比 + **LLM-as-Judge 生成质量打分**（忠实度/相关性），每次优化用数据验证，报告可复现（docs/eval/）；
- 实现 **Agent 工具闭环**：Function Calling 循环 + 工具注册框架（计算器/维基百科联网搜索），max_turns 防死循环，前端展示调用记录；
- 追问改写（指代词检测自动补全上文）、jieba 中文分词（可插拔）、检索结果 TTL 缓存、按 IP 令牌桶限流、JSON 结构化日志；
- 工程化：**70 个 pytest 用例全离线可跑**、Ruff 静态检查、GitHub Actions CI（lint+test+build）、Docker Compose 生产部署（nginx 反代 + SSE 关缓冲）；
- 前端 React + TypeScript：流式对话、Markdown 渲染、引用/工具调用/改写可视化、会话持久化、文档分块查看。

## English Version

**DocWise — RAG + Agent Knowledge Q&A Platform with Evaluation** | Solo Developer | 2025.XX – Present

- Built a full-pipeline RAG system (txt/md/pdf parsing → heading-aware chunking → embedding → BM25+vector hybrid retrieval → reranking → SSE streaming) with clickable citation tracing;
- Curated a 32-question test set and an evaluation framework: 4-mode retrieval hit-rate comparison (top-1: pure-vector 96.9% → hybrid 100%) + LLM-as-Judge faithfulness/relevance scoring, with reproducible reports (docs/eval/);
- Implemented a Function-Calling agent loop with a tool registry (calculator / Wikipedia search), call-limit guard, and a frontend tool-call trace;
- Follow-up query rewriting (pronoun-aware), pluggable jieba tokenization, TTL retrieval cache, per-IP token-bucket rate limiting, structured JSON logging;
- Engineering: 70 offline-runnable pytest cases, Ruff linting, GitHub Actions CI (lint+test+build), Docker Compose production deployment (nginx reverse proxy with SSE buffering disabled);
- Frontend: React + TypeScript with streaming chat, Markdown rendering, citation/tool/rewrite visualization, session persistence, chunk viewer.

## 真实评测数据（2026-08 实测，写进简历时合并到项目条目）

- **检索命中率（top-1 严格模式）**：32 条测试集 / 10 篇语料，**纯向量 96.9% → 混合检索 100%**（真实 embedding：bge-m3；bge-reranker API 同样 100%）
- **生成质量（LLM-as-Judge）**：引用命中 100% / 忠实度 0.99 / 相关性 0.95（DeepSeek 判分，32 题）
- **评测抓 bug 案例 1**：忠实度 0.25 → 定位为引用预览截断污染判分上下文 → 修复后 0.99
- **评测抓 bug 案例 2**：top-1 时纯向量漏检「Transformer 为什么是大模型的基石」（被语义相近的"大模型笔记"带偏）→ 混合检索靠 BM25 精确关键词修正——量化了混合检索的价值
- 待补：真实知识库规模（如「50 篇笔记 / 500+ 分块」）、在线 Demo 地址、GitHub 仓库链接

## 面试一句话总结（30 秒电梯演讲）

「我独立做了一个 RAG + Agent 的知识库问答平台，重点不是调 API，而是把全链路做扎实：
自研 BM25 混合检索、Rerank、追问改写、工具调用闭环都有实现；更关键的是我搭了评测体系——
测试集 + 命中率对比 + LLM 判分，每次优化都有数据证明。实测 32 题检索 top-1 命中率 100%、
生成质量 0.99，评测还帮我抓出过引用截断误判和跨主题漏检两个真实 bug。整个项目 70 个测试
全离线可跑，有 CI、Docker 部署，代码都在 GitHub。」
