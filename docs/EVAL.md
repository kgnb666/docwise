# 评测体系说明（EVAL）

> 这个项目区别于课程作业的核心：**效果可量化、优化有依据**。

## 1. 为什么做评测

RAG 链路长（分块 → 嵌入 → 检索 → 重排 → 生成），任何一环出问题都很难肉眼发现。
没有评测，"优化"就是玄学。评测解决三个问题：
1. 基线是多少？（改之前先量）
2. 改完有没有变好？（同一份测试集前后对比）
3. 坏在哪一环？（检索坏还是生成坏，分层定位）

## 2. 指标定义

| 指标 | 含义 | 怎么测 |
|---|---|---|
| **命中率 recall** | 期望来源文档是否出现在检索结果的 top-k 里 | 自建测试集（问题 + 期望来源），离线可跑 |
| **忠实度 faithfulness** | 回答是否严格基于检索资料（幻觉多寡） | LLM-as-Judge：把 问题/回答/资料 交给 Judge 打分 |
| **相关性 relevance** | 回答与问题切题程度 | LLM-as-Judge 打分 |

## 3. 测试集与语料

- 语料：`backend/samples/*.md`（**20 篇专业面试笔记，85 块**，含主题重叠文档制造检索难度）
- 测试集：`backend/tests/data/test_set.json`，**52 条 QA**（改写题/精确术语题/跨主题易混淆题）
- 扩充方式：真实知识库内容进来后，按同样格式继续加

## 4. 当前结果（真实 API，2026-08 实测）

### 4.1 检索命中率（真实 embedding：硅基流动 BAAI/bge-m3）

**top-k=1（严格模式，能看出差距）**

```
语料 85 块 | 测试集 52 条 | top-k=1 | 分词 jieba
纯向量检索                  50/52  96.2%
混合检索                    51/52  98.1%
混合+OverlapRerank         51/52  98.1%
混合+bge-reranker(API)     51/52  98.1%
```

**top-k=5（宽松模式，全部 100%）**：top-k 越大指标越容易饱和，
评测方法论要点：**指标要选能暴露差距的粒度**（见下）。

### 4.1.1 真实的对比案例（面试可讲）

**案例 1（混合检索的价值）**：top-1 时纯向量漏掉「Transformer 为什么是大模型的基石」——
纯向量被 `llm-notes.md`（大模型笔记）带偏；**混合检索靠 BM25 的精确关键词命中
`deep-learning-notes.md` 修正了结果**（bge-reranker 同样正确）。

**案例 2（诚实的边界）**：两题所有配置都漏了——
- 「动态规划/回溯」被 `spring-notes.md` 的"回调"语义带偏；
- 「怎么评估问答系统忠不忠实」被 `ml-notes.md` 的"评估指标"带偏。
结论：评测体系不只证明优化有效，也**如实暴露当前方案的边界**——这正是数据可信的来源。

### 4.2 生成质量（LLM-as-Judge：DeepSeek 判分，52 题实测）

```
recall（引用命中）    = 100.0%
faithfulness（忠实度）= 0.99
relevance（相关性）   = 0.95
```

> 说明：top-k 越大指标越容易饱和；区分度来自**主题重叠的大语料 + 严格 top-k + 易混淆题**。

### 4.3 评测抓到的真实 Bug（最有价值的产出）

评测体系第一次实战就抓到一个方法论 bug：
- **现象**：忠实度仅 0.25，Judge 判定"回答严重编造"；
- **定位**：引用片段在前端预览时被截断到 200 字符，恰好切掉了回答所依据的关键段落，
  Judge 看到的上文不完整 → 误判；
- **修复**：`RagPipeline` 增加 `citation_preview_len` 参数——前端预览仍 200，
  评测用 2000 拿完整上下文；
- **结果**：忠实度 0.25 → **0.99**。

> 面试价值：这不是"效果很好"的自夸，而是**评测体系如何发现并量化修复一个真实缺陷**的完整链路。

## 5. 两套分词实现对比

`TOKENIZER=auto|legacy|jieba`（`.env`）：
- legacy：零依赖，中文按「单字+二元组」；
- jieba：真实中文分词，对复杂语料更准；装了即用（auto 自动启用）。

当前示例语料下两者命中率均为 100%；真实中文语料（课程笔记/面试题）
通常 jieba 更优——换真实内容后再跑 `python scripts/run_eval.py --tokenizer jieba` 对比。

## 6. 评测命令

```bash
# 离线检索命中率（无需 Key）
python scripts/run_eval.py                          # 默认分词
python scripts/run_eval.py --tokenizer jieba        # jieba 分词
python scripts/run_eval.py --embedding openai       # 真实 embedding（需 Key）

# 生成质量（LLM-as-Judge，需 Key）
python scripts/run_eval_quality.py
```

报告输出：`docs/eval/offline_report.json` / `docs/eval/quality_report.json`

## 7. 下一步（真实语料驱动）

1. ✅ 真实 embedding（硅基流动 bge-m3）+ 四档对比已跑通（top-1 有区分度：96.9%→100%）
2. ✅ LLM-as-Judge 生成质量已跑通（忠实度/相关性 0.99/0.95，含"截断 Bug"修复案例）
3. ✅ bge-reranker（云端 API）已接入第四档对比
4. 真实知识库内容扩充测试集至 50+ 条（区分度曲线的关键）
5. 接入 RAGAS 库做归一化聚合，与自研指标交叉验证
