"""Rerank 配置切换测试：reranker=api 时依赖注入返回 APIReranker，并正确回退 URL/Key。"""

from app import deps
from app.config import Settings
from app.deps import get_reranker
from app.rag.reranker import APIReranker, NullReranker, OverlapReranker


def test_settings_rerank_api_env_vars(monkeypatch):
    monkeypatch.setenv("RERANK_BASE_URL", "https://rerank.example.com/v1")
    monkeypatch.setenv("RERANK_API_KEY", "sk-rerank")
    monkeypatch.setenv("RERANK_MODEL", "BAAI/bge-reranker-base")
    monkeypatch.setenv("RERANK_TOP_N", "5")

    s = Settings()
    assert s.rerank_base_url == "https://rerank.example.com/v1"
    assert s.rerank_api_key == "sk-rerank"
    assert s.rerank_model == "BAAI/bge-reranker-base"
    assert s.rerank_top_n == 5


def test_get_reranker_api_uses_rerank_config(monkeypatch):
    monkeypatch.setattr(deps._settings, "reranker", "api")
    monkeypatch.setattr(deps._settings, "rerank_base_url", "https://rerank.example.com/v1")
    monkeypatch.setattr(deps._settings, "rerank_api_key", "sk-rerank")
    monkeypatch.setattr(deps._settings, "rerank_model", "BAAI/bge-reranker-v2-m3")
    monkeypatch.setattr(deps._settings, "rerank_top_n", 3)

    reranker = get_reranker()
    assert isinstance(reranker, APIReranker)
    assert reranker.base_url == "https://rerank.example.com/v1"
    assert reranker.api_key == "sk-rerank"
    assert reranker.top_n == 3


def test_get_reranker_api_falls_back_to_embedding_then_openai(monkeypatch):
    monkeypatch.setattr(deps._settings, "reranker", "api")
    monkeypatch.setattr(deps._settings, "rerank_base_url", "")
    monkeypatch.setattr(deps._settings, "rerank_api_key", "")
    monkeypatch.setattr(deps._settings, "embedding_base_url", "https://embed.example.com/v1")
    monkeypatch.setattr(deps._settings, "embedding_api_key", "sk-embed")
    monkeypatch.setattr(deps._settings, "openai_base_url", "https://openai.example.com/v1")
    monkeypatch.setattr(deps._settings, "openai_api_key", "sk-openai")

    reranker = get_reranker()
    assert isinstance(reranker, APIReranker)
    assert reranker.base_url == "https://embed.example.com/v1"
    assert reranker.api_key == "sk-embed"

    monkeypatch.setattr(deps._settings, "embedding_base_url", "")
    monkeypatch.setattr(deps._settings, "embedding_api_key", "")
    reranker2 = get_reranker()
    assert reranker2.base_url == "https://openai.example.com/v1"
    assert reranker2.api_key == "sk-openai"


def test_get_reranker_overlap_is_default_offline(monkeypatch):
    """默认（overlap）保持离线零依赖：不构造任何外部 API 客户端。"""
    monkeypatch.setattr(deps._settings, "reranker", "overlap")
    assert isinstance(get_reranker(), OverlapReranker)


def test_get_reranker_null_returns_identity(monkeypatch):
    monkeypatch.setattr(deps._settings, "reranker", "null")
    assert isinstance(get_reranker(), NullReranker)
