# 12 周开发路线图

> 目标：产出**可部署、可演示、可量化**的完整项目，并准备好简历条目、演示视频与面试话术。
> 每周建议投入 8~10 小时（可灵活伸缩）。每个阶段结束都应有**可见成果**。

## 阶段 0：基础补课与骨架（第 1 周）

- [ ] 环境：安装 Python 3.12（若 3.14 遇包问题）、Node、Git、Docker Desktop
- [ ] 跑通项目骨架：后端 `uvicorn` 启动 + 前端 `npm run dev` 启动
- [ ] 补课：Python 异步（async/await）、FastAPI 路由与请求模型、REST 概念
- [ ] Git 初始化并完成第一次 commit；学会分支与 PR（为 CI 做准备）

**里程碑**：本地能启动前后端，访问到健康检查接口。

## 阶段 1：MVP 跑通（第 2~4 周）

- [x] 文档上传接口：txt / md / **pdf**（pypdf 提取文本，空内容/扫描件有明确报错）
- [x] 分块器：标题感知 + 重叠窗口，能正确处理中文
- [x] 嵌入服务：OpenAI 兼容接口 + **离线哈希嵌入（EMBEDDING_PROVIDER=hash，无需 Key 可跑通全链路）**
- [x] 向量存储：内存实现（接口先行，为替换留口子）
- [x] 聊天接口：检索 → 组装 Prompt → **流式**回答（SSE）
- [x] 前端：聊天界面（消息流、加载态、错误提示）
- [x] 引用溯源：回答下方展示来源文档与片段
- [x] 单元测试：分块边界、检索排序、端到端上传（12+ 用例）
- [x] **离线评测脚本**：纯向量 vs 混合检索命中率对比（scripts/run_eval.py → docs/eval/）

**里程碑**：上传文档后能问答，回答带引用出处。**先能跑，再谈优化。**

## 阶段 2：深度优化（第 5~8 周）⭐ 拉开差距的核心阶段

### 检索质量
- [x] BM25 关键词检索（自研轻量实现，零依赖）
- [x] 混合检索：BM25 + 向量加权融合（alpha 可调）
- [x] Rerank 精排（OverlapReranker 轻量实现；接口预留，后续换 bge-reranker）
- [x] 追问改写：指代词检测 + 上文拼接扩展（query_rewrite.py，可换 LLM 改写）

### 评测体系（差异化亮点）
- [x] 自建测试集（8 条种子，随真实内容扩充）
- [x] 离线命中率对比：纯向量 vs 混合 vs 混合+Rerank（scripts/run_eval.py）
- [x] LLM-as-Judge 生成质量框架（忠实度/相关性，scripts/run_eval_quality.py，离线可测）
- [ ] 用真实 Key 跑生成质量评测，产出可写进简历的完整报告（框架已就绪，待 Key）

### Agent 能力
- [x] 工具注册框架：`(name, description, schema, handler)`，支持同步/异步
- [x] 内置工具：计算器 + 维基百科搜索（免费 API 演示联网能力）
- [x] Function Calling 循环：流式聚合分片 tool_call → 执行 → 回填 → 续答，max_turns 防死循环
- [x] Agent 模式下回答仍带引用，前端展示"🔧 调用了 XX 工具"记录

### 工程化
- [x] 检索结果缓存（InMemoryTTL，接口预留 Redis）：热点问题跳过 embedding 调用
- [x] 令牌桶限流（按 IP，429 兜底）：防止 LLM Key 被刷爆
- [x] 结构化日志埋点（JSON Lines → logs/app.log）：query / 耗时 / 错误
- [x] Ruff 静态检查（配置 + CI 步骤，0 告警）
- [x] GitHub Actions CI 配置（ruff + pytest + 前端构建，待推送验证）
- [ ] Redis 集中式缓存/限流（多实例部署时）、OpenTelemetry 链路追踪

**里程碑**：评测报告有数据对比曲线；Agent 能完成"查资料并总结"的演示。

## 阶段 3：产品化与求职包装（第 9~12 周）

- [x] 前端会话持久化（localStorage，刷新不丢）+ 清空对话
- [x] 文档分块查看 UI（🧩 弹层，演示"知识如何被切分"）
- [x] 生产级部署体系：nginx 反代（SSE 关缓冲）+ 两阶段镜像 + docker-compose 生产模式
- [x] 部署指南（docs/DEPLOYMENT.md：VPS/Docker/HTTPS/排查）
- [x] 文档分块查看 API（GET /api/documents/{id}/chunks）
- [ ] 前端完善：引用高亮、历史会话、文档管理页、设置页
- [ ] 接入真实知识库内容（你定的领域）
- [ ] 云服务器实测上线（有可访问的 Demo URL）
- [x] 面试题库（docs/INTERVIEW.md，22 问含答案）
- [x] 3 分钟演示脚本（docs/DEMO_SCRIPT.md，含录制清单）
- [ ] README 完善：架构图、评测数据、演示截图
- [ ] 简历条目：用 STAR 结构写项目经历（见 docs/RESUME.md 模板）
- [ ] 录制 3 分钟演示视频
- [ ] 面试话术：过一遍 docs/INTERVIEW.md

**里程碑**：可访问的在线 Demo + 完整简历条目 + 演示视频。

## 面试官爱问的问题（提前准备）

1. 为什么用混合检索而不是纯向量检索？数据呢？
2. 分块大小怎么定的？中文和英文有区别吗？
3. 评测指标具体怎么算的？怎么保证测试集可信？
4. 向量存储为什么从内存换到 FAISS/Milvus？规模多大触发？
5. Agent 的工具调用循环怎么防止死循环？怎么限次？
6. 流式输出怎么实现的？断线怎么办？
7. 如果知识库里没有答案，系统会怎么表现？怎么处理幻觉？
8. 并发上来之后性能瓶颈在哪？你怎么定位的？
