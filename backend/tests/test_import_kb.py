"""知识库导入工具测试（离线：哈希嵌入 + 示例语料）。"""

import asyncio
from pathlib import Path

from app.rag.embedder_hash import HashEmbedder
from app.storage.document_store import get_document_store, reset_document_store
from app.storage.vector_store import get_vector_store, reset_vector_store
from scripts.import_kb import import_kb, read_text

SAMPLES = Path(__file__).resolve().parents[1] / "samples"


def _reset():
    reset_vector_store()
    reset_document_store()


def test_import_directory():
    _reset()
    result = asyncio.run(import_kb([str(SAMPLES)], HashEmbedder()))
    assert result["documents"] >= 10  # 10 篇示例文档
    assert result["chunks"] > 0
    assert get_vector_store().count() == result["chunks"]
    assert get_document_store().count() == result["documents"]


def test_import_single_file():
    _reset()
    f = SAMPLES / "rag-notes.md"
    result = asyncio.run(import_kb([str(f)], HashEmbedder()))
    assert result["documents"] == 1
    assert result["items"][0]["name"] == "rag-notes.md"


def test_read_text_markdown():
    text = read_text(SAMPLES / "rag-notes.md")
    assert "RAG" in text
