# DocWise 评测总结（自动生成）

> 生成时间：2026-08-14 22:52

## 检索命中率（真实 embedding）

| 配置 | 命中 | 准确率 |
|---|---|---|
| 纯向量检索 | 31/32 | 96.9% |
| 混合检索 | 32/32 | 100.0% |
| 混合+OverlapRerank | 32/32 | 100.0% |
| 混合+bge-reranker(API) | 32/32 | 100.0% |

- 语料：40 块 | 测试集：C:\Users\kgnb666.DESKTOP-55DCFH3.003\Desktop\dp\backend\tests\data\test_set.json | top-k=1 | 分词：jieba

## 生成质量（LLM-as-Judge）

- 引用命中 recall：**100.0%**
- 忠实度 faithfulness：**0.99**
- 相关性 relevance：**0.95**

## 基准（延迟 / 成本）

- 单次问答平均延迟：**1885ms**
- 单次问答平均成本：**约 ¥0.00374**
- 单次查询嵌入：293.4ms
- 价格估算口径：输入 ¥2.0/M token、输出 ¥8.0/M、嵌入 ¥0.8/M（以官网实时价为准）；token 数按字符数/1.5 粗估。
