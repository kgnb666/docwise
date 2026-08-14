"""SSE 流式接口事件协议测试：验证前端依赖的事件顺序与兜底。"""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.deps import get_embedder
from app.main import app
from app.rag.embedder_hash import HashEmbedder
from app.storage.document_store import reset_document_store
from app.storage.vector_store import reset_vector_store

SAMPLES = Path(__file__).resolve().parents[1] / "samples"
RAG_NOTES = (SAMPLES / "rag-notes.md").read_text(encoding="utf-8")


@pytest.fixture(autouse=True)
def _isolated():
    reset_vector_store()
    reset_document_store()
    app.dependency_overrides[get_embedder] = lambda: HashEmbedder()
    yield
    app.dependency_overrides.pop(get_embedder, None)
    reset_vector_store()
    reset_document_store()


def _parse_sse(text: str) -> list[dict]:
    events = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("data:"):
            continue
        payload = line[5:].strip()
        if payload == "[DONE]":
            continue
        events.append(json.loads(payload))
    return events


def test_stream_followup_event_order():
    """有文档 + 追问 + 无 Key：query_rewritten → citations → error。"""
    client = TestClient(app)
    resp = client.post(
        "/api/documents", files={"file": ("rag-notes.md", RAG_NOTES, "text/markdown")}
    )
    assert resp.status_code == 200

    with client.stream(
        "POST",
        "/api/chat/stream",
        json={
            "query": "它有哪些优点",
            "history": [
                {"role": "user", "content": "什么是RAG"},
                {"role": "assistant", "content": "RAG是检索增强生成"},
            ],
        },
    ) as stream:
        body = "".join(stream.iter_text())

    events = _parse_sse(body)
    types = [e["type"] for e in events]
    assert types[0] == "query_rewritten"
    assert "citations" in types
    assert types[-1] == "error"  # 无 Key → LLM 失败 → error 事件兜底（不崩溃）


def test_stream_empty_store_fallback():
    """空知识库：citations(空) → 兜底提示 delta → done。"""
    client = TestClient(app)
    with client.stream(
        "POST", "/api/chat/stream", json={"query": "你好", "history": []}
    ) as stream:
        body = "".join(stream.iter_text())

    events = _parse_sse(body)
    types = [e["type"] for e in events]
    assert types == ["citations", "delta", "done"]
    assert "还没有相关内容" in events[1]["content"]
