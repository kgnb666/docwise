"""结构化日志关键路径测试：query_id / 命中数 / 评测指标，且不泄露内容与 Key。"""

import asyncio
import logging
from logging.handlers import RotatingFileHandler

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.core.cache import InMemoryTTLCache
from app.core.observability import JsonFormatter, new_query_id, setup_logging, truncate
from app.eval.judge import LLMJudge
from app.eval.runner import QualityEvaluator
from app.rag.pipeline import RagPipeline
from app.rag.retriever import Retriever
from app.storage.vector_store import InMemoryVectorStore


class CapturingHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


@pytest.fixture
def captured():
    logger = logging.getLogger("docwise")
    old_level = logger.level
    logger.setLevel(logging.INFO)
    handler = CapturingHandler()
    logger.addHandler(handler)
    yield handler
    logger.removeHandler(handler)
    logger.setLevel(old_level)


class _SpyEmbedder:
    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] for _ in texts]


def _pipeline(with_cache: bool = False) -> RagPipeline:
    store = InMemoryVectorStore()
    store.add(
        "c1",
        [1.0, 0.0],
        {"doc_id": "d1", "doc_name": "a.md", "index": 0, "text": "机密内容MARKER不要落日志"},
    )
    retriever = Retriever(store, top_k=2, rerank_top_k=2, alpha=0.0)
    return RagPipeline(
        _SpyEmbedder(),
        retriever,
        Settings(embedding_provider="hash"),
        retrieval_cache=InMemoryTTLCache(ttl=60) if with_cache else None,
    )


def _serialized(handler: CapturingHandler) -> str:
    return "\n".join(JsonFormatter().format(r) for r in handler.records)


def test_retrieval_log_has_query_id_and_hits_without_content(captured):
    p = _pipeline()
    chunks = asyncio.run(p._retrieve("问题", query_id="qid123"))
    assert chunks

    events = [r for r in captured.records if getattr(r, "event", None) == "retrieval"]
    assert events
    fields = events[0].fields
    assert fields["query_id"] == "qid123"
    assert fields["hit_count"] == 1
    assert fields["top_score"] is not None
    assert fields["cache_hit"] is False
    assert "latency_ms" in fields

    lines = _serialized(captured)
    # 日志只记结构化字段，不写入完整检索片段（防 prompt / 敏感内容泄露）
    assert "机密内容MARKER" not in lines
    assert "sk-" not in lines


def test_retrieval_cache_hit_logged(captured):
    p = _pipeline(with_cache=True)
    asyncio.run(p._retrieve("问题", query_id="q1"))
    asyncio.run(p._retrieve("问题", query_id="q2"))

    events = [r for r in captured.records if getattr(r, "event", None) == "retrieval"]
    assert [e.fields["cache_hit"] for e in events] == [False, True]
    assert events[1].fields["query_id"] == "q2"


def test_eval_log_has_query_id_and_metrics(captured):
    class FakeCompleter:
        async def complete(self, messages: list[dict]) -> str:
            return '{"score": 0.8, "reason": "ok"}'

    class FakeAnswerer:
        async def chat(self, query: str, history: list[dict] | None = None) -> dict:
            return {
                "answer": "回答内容",
                "citations": [{"doc_name": "rag-notes.md", "text": "资料文本"}],
                "tools": [],
            }

    report = asyncio.run(
        QualityEvaluator(FakeAnswerer(), LLMJudge(FakeCompleter())).run(
            [{"question": "什么是RAG", "expected_doc": "rag-notes.md"}]
        )
    )
    assert report["recall"] == 1.0

    events = [r for r in captured.records if getattr(r, "event", None) == "eval_item"]
    assert events
    fields = events[0].fields
    assert fields["query_id"]
    assert fields["hit"] is True
    assert fields["faithfulness"] == 0.8
    assert fields["relevance"] == 0.8
    assert "latency_ms" in fields


def test_chat_error_log_has_query_id_without_key(captured):
    from app.deps import get_pipeline
    from app.main import app

    class BoomPipeline:
        async def chat(
            self, query: str, history: list[dict] | None = None, query_id: str | None = None
        ) -> dict:
            raise RuntimeError("boom-内部错误")

    app.dependency_overrides[get_pipeline] = lambda: BoomPipeline()
    try:
        resp = TestClient(app).post("/api/chat", json={"query": "问题", "history": []})
        assert resp.status_code == 502
    finally:
        app.dependency_overrides.pop(get_pipeline, None)

    events = [r for r in captured.records if getattr(r, "event", None) == "chat_error"]
    assert events
    fields = events[0].fields
    assert fields["query_id"]
    assert "boom" in fields["error"]

    lines = _serialized(captured)
    assert "sk-" not in lines
    assert "Bearer" not in lines


def test_new_query_id_unique_and_truncate():
    assert new_query_id() != new_query_id()
    assert truncate("短文本") == "短文本"
    assert len(truncate("x" * 300)) <= 201  # 200 字符 + 省略号
    assert truncate(None) == ""


def test_setup_logging_uses_rotating_file_handler(tmp_path):
    """验证日志初始化配置了 RotatingFileHandler，且单文件上限为 10MB，保留 5 个备份。"""
    logger = logging.getLogger("docwise")
    old_handlers = list(logger.handlers)
    logger.handlers.clear()
    try:
        setup_logging(tmp_path)
        rotating = [h for h in logger.handlers if isinstance(h, RotatingFileHandler)]
        assert len(rotating) == 1
        handler = rotating[0]
        assert handler.maxBytes == 10 * 1024 * 1024
        assert handler.backupCount == 5
    finally:
        logger.handlers = old_handlers

