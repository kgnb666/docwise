# 内置知识库：计算机面试知识库（20 篇）

项目自带 **20 篇专业级面试笔记**作为内置知识库，覆盖大厂实习面试高频考点——
既用于演示/评测系统，也可以直接当你的**面试复习资料**。

## 按主题分类

| 类别 | 文档 |
|---|---|
| **AI / 大模型** | `rag-notes.md`（RAG）、`llm-notes.md`（大模型/提示工程）、`ml-notes.md`（机器学习）、`deep-learning-notes.md`（深度学习） |
| **Java 后端** | `java-notes.md`（JVM/集合/GC）、`spring-notes.md`（IoC/AOP/自动装配）、`concurrency-notes.md`（并发/锁/线程池）、`design-pattern-notes.md`（设计模式） |
| **基础四大件** | `network-notes.md`（网络）、`os-notes.md`（操作系统）、`db-notes.md`（数据库）、`algo-notes.md`（数据结构与算法） |
| **中间件 / 分布式** | `redis-notes.md`（Redis）、`mq-notes.md`（消息队列）、`distributed-notes.md`（分布式基础） |
| **工程与系统** | `git-notes.md`、`docker-notes.md`、`frontend-notes.md`（前端基础）、`system-design-notes.md`（系统设计）、`python-notes.md` |

## 用法

1. **开箱即用**：`scripts/run_eval.py` / `run_eval_quality.py` 用它跑评测；
2. **复习面试**：直接当八股文笔记背，重点是能结合自己项目讲（见 `docs/INTERVIEW.md`）；
3. **替换/扩充为个人知识库**：把自己资料放一个文件夹，
   `python scripts/import_kb.py <文件夹>` 一键导入，然后按 `tests/data/test_set.json`
   的格式追加测试题（每道标注期望来源文档），重跑评测。

## 评测测试集

`backend/tests/data/test_set.json`（52 条 QA）覆盖全部 20 篇文档。
