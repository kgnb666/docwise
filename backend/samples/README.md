# 内置示例知识库：计算机面试知识笔记

这 10 篇 Markdown 是项目自带的**示例知识库**，主题覆盖计算机实习面试高频考点，
用来演示/评测系统（也正好可以当你的面试复习资料）：

| 文件 | 主题 |
|---|---|
| `rag-notes.md` | RAG 检索增强生成（本项目核心技术） |
| `llm-notes.md` | 大模型与提示工程 / 幻觉 / Function Calling |
| `ml-notes.md` | 机器学习基础（过拟合 / 评估指标） |
| `deep-learning-notes.md` | 深度学习（反向传播 / Transformer） |
| `db-notes.md` | 数据库（事务 ACID / B+ 树索引 / 慢查询） |
| `network-notes.md` | 计算机网络（TCP / HTTPS / 状态码） |
| `os-notes.md` | 操作系统（进程线程 / 死锁 / 内存） |
| `python-notes.md` | Python 基础（数据结构 / 装饰器 / 异步） |
| `git-notes.md` | Git 与协作（分支 / rebase / CI） |
| `docker-notes.md` | Docker 与部署（镜像 / compose / 上线） |

## 用途

1. **开箱即用**：`scripts/run_eval.py` / `run_eval_quality.py` 用它们跑评测；
2. **上手体验**：启动前后端后，把这些文档上传就能问答；
3. **替换为真实知识库**：把自己的资料放进一个文件夹，
   运行 `python scripts/import_kb.py <文件夹>` 一键导入（`docs/CHECKLIST.md` 有完整流程）。

## 评测测试集

`backend/tests/data/test_set.json`（32 条 QA）针对这 10 篇文档标注了期望来源，
导入真实知识库后请按同样格式扩充。
