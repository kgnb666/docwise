"""LLM-as-Judge 生成质量评测（RAGAS 风格）。

指标（面试可讲：RAG 系统"生成得好不好"如何量化）：
- faithfulness 忠实度：回答是否严格基于检索到的资料（幻觉越少分越高）；
- answer_relevance 答案相关性：回答与问题的相关程度。

实现：把 (question, answer, context) 交给 Judge LLM，要求输出 JSON 分数与理由。
离线可测：Judge 只依赖 `complete(messages) -> str`，测试里注入假实现即可。

阶段 3 演进：接入 RAGAS 库的归一化与聚合（当前为自研轻量实现，指标口径一致）。
"""

from __future__ import annotations

import json
import re
from typing import Protocol

_FAITHFULNESS_PROMPT = """你是严谨的 RAG 系统评测员。请判断「回答」是否忠实于「参考资料」。

规则：
- 回答中的每个关键事实，必须能在参考资料中找到依据；
- 编造、与资料矛盾、答非所问的内容越多，分数越低；
- 参考资料中没有的信息，回答却说得很具体，属于严重不忠实。

输出严格 JSON（不要输出其他内容）：{{"score": 0到1之间的小数, "reason": "一句话理由"}}

参考资料：
{context}

回答：
{answer}
"""

_RELEVANCE_PROMPT = """你是严谨的 RAG 系统评测员。请判断「回答」与「问题」的相关程度。

规则：
- 完全切题、直击问题核心 → 高分；
- 相关但不够直接/不完整 → 中等分；
- 跑题或答非所问 → 低分。

输出严格 JSON（不要输出其他内容）：{{"score": 0到1之间的小数, "reason": "一句话理由"}}

问题：{question}
回答：{answer}
"""


class Completer(Protocol):
    async def complete(self, messages: list[dict]) -> str: ...


def parse_score_output(raw: str) -> tuple[float, str]:
    """解析 Judge 输出：优先取 JSON 的 score/reason；失败则退回启发式解析。"""
    raw = raw.strip()
    # 1) 尝试整体 JSON
    try:
        obj = json.loads(raw)
        score = float(obj.get("score", 0.0))
        reason = str(obj.get("reason", ""))
        return max(0.0, min(1.0, score)), reason
    except (ValueError, TypeError):
        pass
    # 2) 尝试从文本中提取 JSON 片段
    m = re.search(r"\{[^{}]*\"score\"[^{}]*\}", raw)
    if m:
        try:
            obj = json.loads(m.group(0))
            return max(0.0, min(1.0, float(obj.get("score", 0.0)))), str(obj.get("reason", ""))
        except (ValueError, TypeError):
            pass
    # 3) 启发式：提取 "X/10" 或 "X 分"
    m = re.search(r"(\d+(?:\.\d+)?)\s*/\s*10", raw)
    if m:
        return max(0.0, min(1.0, float(m.group(1)) / 10.0)), "启发式解析"
    return 0.0, "解析失败"


class LLMJudge:
    """用 LLM 给 (问题, 回答, 上下文) 打分。"""

    def __init__(self, completer: Completer):
        self._complete = completer.complete

    async def faithfulness(self, question: str, answer: str, context: str) -> tuple[float, str]:
        prompt = _FAITHFULNESS_PROMPT.format(context=context[:4000], answer=answer[:2000])
        raw = await self._complete(
            [{"role": "user", "content": prompt}]
        )
        return parse_score_output(raw)

    async def answer_relevance(self, question: str, answer: str) -> tuple[float, str]:
        prompt = _RELEVANCE_PROMPT.format(question=question[:1000], answer=answer[:2000])
        raw = await self._complete([{"role": "user", "content": prompt}])
        return parse_score_output(raw)
