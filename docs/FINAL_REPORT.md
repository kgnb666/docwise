# DocWise 项目完成报告

> 本文档总结项目全貌，映射原始目标：**做一个让面试官眼前一亮的高竞争力实习项目**。

## 一、项目一句话

**DocWise**：带评测体系的 RAG + Agent 知识库问答平台——上传任意文档，
即可获得可对话、可溯源、能调用工具（联网搜索/计算）的 AI 助手，
且每一项能力都有真实评测数据支撑。

## 二、目标达成情况

| 原始要求 | 达成情况 |
|---|---|
| AI/大模型应用 | ✅ RAG 全链路 + Agent Function Calling + LLM-as-Judge |
| 后端 | ✅ FastAPI 异步 + SSE 流式 + 70 个单元测试 + Ruff 0 告警 |
| 前端 | ✅ React + TS：流式对话 / Markdown / 引用溯源 / 工具与改写可视化 |
| 可部署 | ✅ 生产 nginx + 两阶段镜像 + docker-compose + DEPLOYMENT 指南 |
| 可演示 | ✅ 内置 10 篇面试知识库 + import_kb 一键导入 + DEMO 分镜脚本 |
| 可量化效果 | ✅ 真实评测数据（见下）+ 评测体系抓到 2 个真实 bug |
| 简历条目 / 面试话术 | ✅ RESUME 写实版 + INTERVIEW 24 问 + 30 秒电梯演讲 |

## 三、真实评测数据（2026-08 实测，全部可复现）

```
检索命中率（top-1，32 题，bge-m3 真实嵌入）
  纯向量检索            96.9%  ← 漏 1 题（Transformer 跨主题）
  混合检索             100.0%  ← BM25 关键词纠偏
  混合+OverlapRerank   100.0%
  混合+bge-reranker(API) 100.0%

生成质量（32 题，DeepSeek 判分）
  引用命中 100% · 忠实度 0.99 · 相关性 0.95

基准
  单次问答约 2.3s · 成本约 ¥0.0034/次
```

复现：`powershell -ExecutionPolicy Bypass -File scripts/run_all.ps1`（约 ¥1-2 花费）

## 四、评测体系抓到的事实（面试核心故事线）

1. **引用截断误判**：忠实度 0.25 → 定位为引用预览截断污染判分上下文 → 修复后 0.99
2. **Transformer 跨主题漏检**：纯向量被语义相近文档带偏 → 混合检索修正
   → 量化了混合检索的价值

## 五、技术栈与规模

- 后端 Python/FastAPI；LLM DeepSeek；嵌入 bge-m3（硅基流动）；Rerank bge-reranker（API）
- 70 个单元测试（全离线、不耗 Key）、Ruff 0 告警、GitHub Actions CI 配置
- 检索缓存 / 令牌桶限流 / JSON 结构化日志 / 追问改写 / jieba 分词 / 双 API 配置

## 六、架构演进留白（面试"如果重做"题）

内存向量库 → FAISS/pgvector/Milvus；OverlapReranker → bge-reranker（已留接口）；
单机限流 → Redis 集中式；JSON 日志 → OpenTelemetry。

## 七、剩余事项（用户侧，见 docs/CHECKLIST.md）

1. 导入真实知识库（`python scripts/import_kb.py <文件夹>`）
2. 装 git → 推 GitHub 触发 CI
3. 云服务器上线（DEPLOYMENT.md）→ 录 3 分钟演示视频（DEMO_SCRIPT.md）
4. 按 RESUME.md 填真实数据投递

## 八、给用户的投递前提醒

- `.env` 含真实 API Key，已被 .gitignore 排除——推送前 `git status` 确认
- Key 若担心泄露，可到平台重置
