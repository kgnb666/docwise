"""评测执行器：测试集 → 系统作答 → 判分 → 聚合报告。

指标：
- recall 命中率：期望来源文档是否出现在回答的引用中（检索质量）；
- faithfulness / answer_relevance：LLM-as-Judge 打分（生成质量）。

离线可测：pipeline 与 judge 都是注入的，测试用假实现跑通全流程。
真实运行：python scripts/run_eval_quality.py（需要 API Key）。
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Protocol

from app.eval.judge import LLMJudge


class Answerer(Protocol):
    async def chat(self, query: str, history: list[dict] | None = None) -> dict: ...


@dataclass
class ItemResult:
    question: str
    expected_doc: str
    answer: str
    hit: bool
    top_docs: list[str] = field(default_factory=list)
    faithfulness: float = 0.0
    relevance: float = 0.0
    faithfulness_reason: str = ""
    relevance_reason: str = ""


class QualityEvaluator:
    def __init__(self, answerer: Answerer, judge: LLMJudge):
        self.answerer = answerer
        self.judge = judge

    async def evaluate_one(self, item: dict) -> ItemResult:
        """对单条测试数据：系统作答 → 判分。"""
        question = item["question"]
        expected = item["expected_doc"]

        result = await self.answerer.chat(question, [])
        answer = result.get("answer", "")
        citations = result.get("citations", [])
        top_docs = [c.get("doc_name", "") for c in citations]
        context = "\n".join(c.get("text", "") for c in citations)

        item_result = ItemResult(
            question=question,
            expected_doc=expected,
            answer=answer,
            hit=expected in top_docs,
            top_docs=top_docs,
        )
        if answer and context:
            fs, fs_reason = await self.judge.faithfulness(question, answer, context)
            ar, ar_reason = await self.judge.answer_relevance(question, answer)
            item_result.faithfulness = fs
            item_result.faithfulness_reason = fs_reason
            item_result.relevance = ar
            item_result.relevance_reason = ar_reason
        return item_result

    async def run(self, test_set: list[dict]) -> dict:
        """跑完整测试集，聚合指标。"""
        results = [await self.evaluate_one(item) for item in test_set]
        n = len(results)
        if n == 0:
            return {
                "items": [],
                "recall": 0.0,
                "avg_faithfulness": 0.0,
                "avg_relevance": 0.0,
                "count": 0,
            }

        scored = [r for r in results if r.answer]
        return {
            "items": [
                {
                    "question": r.question,
                    "expected": r.expected_doc,
                    "hit": r.hit,
                    "top_docs": r.top_docs,
                    "faithfulness": r.faithfulness,
                    "relevance": r.relevance,
                    "answer_preview": r.answer[:120],
                }
                for r in results
            ],
            "recall": round(sum(r.hit for r in results) / n, 4),
            "avg_faithfulness": round(
                sum(r.faithfulness for r in scored) / len(scored), 4
            ) if scored else 0.0,
            "avg_relevance": round(
                sum(r.relevance for r in scored) / len(scored), 4
            ) if scored else 0.0,
            "count": n,
        }


def run_quality_eval(answerer: Answerer, judge: LLMJudge, test_set: list[dict]) -> dict:
    """同步入口：直接跑（脚本用）。"""
    return asyncio.run(QualityEvaluator(answerer, judge).run(test_set))
