"""LLM-as-Judge 与评测执行器测试（全程离线，注入假实现）。"""

import asyncio

from app.eval.judge import LLMJudge, parse_score_output
from app.eval.runner import QualityEvaluator


class FakeCompleter:
    """按调用次数返回预置的 Judge 输出。"""

    def __init__(self, responses: list[str]):
        self.responses = responses
        self.calls = 0

    async def complete(self, messages: list[dict]) -> str:
        r = self.responses[min(self.calls, len(self.responses) - 1)]
        self.calls += 1
        return r


class FakeAnswerer:
    """固定回答与引用，避免真实 LLM 调用。"""

    def __init__(self, answer: str, citations: list[dict]):
        self.answer = answer
        self.citations = citations

    async def chat(self, query: str, history: list[dict] | None = None) -> dict:
        return {"answer": self.answer, "citations": self.citations, "tools": []}


# ---------- 分数解析 ----------

def test_parse_score_json():
    assert parse_score_output('{"score": 0.8, "reason": "忠实"}') == (0.8, "忠实")


def test_parse_score_x_of_10():
    s, r = parse_score_output("综合来看 7/10，比较相关")
    assert abs(s - 0.7) < 1e-9
    assert r == "启发式解析"


def test_parse_score_extract_json_from_text():
    raw = '我的判断：{"score": 0.6, "reason": "部分相关"} 完毕'
    s, r = parse_score_output(raw)
    assert abs(s - 0.6) < 1e-9
    assert r == "部分相关"


def test_parse_score_garbage_falls_back():
    assert parse_score_output("完全无法解析的内容") == (0.0, "解析失败")


def test_score_clamped_to_unit_range():
    s, _ = parse_score_output('{"score": 1.7}')
    assert s == 1.0


# ---------- Judge ----------

def test_judge_calls_completer_and_parses():
    judge = LLMJudge(FakeCompleter(['{"score": 0.9, "reason": "ok"}']))
    s, r = asyncio.run(judge.faithfulness("问题", "回答", "资料"))
    assert s == 0.9 and r == "ok"


# ---------- 评测执行器 ----------

def test_quality_evaluator_aggregates():
    judge = LLMJudge(
        FakeCompleter(
            [
                '{"score": 0.8, "reason": "ok"}',  # item1 faithfulness
                '{"score": 0.7, "reason": "ok"}',  # item1 relevance
                '{"score": 0.5, "reason": "ok"}',  # item2 faithfulness
                '{"score": 0.9, "reason": "ok"}',  # item2 relevance
            ]
        )
    )
    answerer = FakeAnswerer(
        "回答内容",
        [{"doc_name": "rag-notes.md", "text": "资料文本"}],
    )
    test_set = [
        {"question": "什么是RAG", "expected_doc": "rag-notes.md"},
        {"question": "Docker 怎么用", "expected_doc": "docker-notes.md"},
    ]

    report = asyncio.run(QualityEvaluator(answerer, judge).run(test_set))

    assert report["count"] == 2
    assert report["recall"] == 0.5  # 只有第一条命中期望来源
    assert report["avg_faithfulness"] == 0.65
    assert report["avg_relevance"] == 0.8
    items = report["items"]
    assert items[0]["hit"] is True
    assert items[1]["hit"] is False


def test_quality_evaluator_empty_set():
    report = asyncio.run(
        QualityEvaluator(FakeAnswerer("", []), LLMJudge(FakeCompleter([]))).run([])
    )
    assert report["count"] == 0
    assert report["recall"] == 0.0
