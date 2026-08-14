"""离线评测（阶段 2 实现）：RAGAS 指标 + 自建测试集。

目标：产出可复现的评测报告，用数据证明检索/排序优化的收益。
- 测试集：20~50 条 {question, ground_truth, expected_doc} 标注数据
- 指标：命中率（Recall）、忠实度（Faithfulness）、答案相关性（Answer Relevance）
- 对比实验：纯向量 vs 混合 vs 混合+Rerank
"""
