"""HTTP 连接池复用与生命周期管理测试。"""

import asyncio

import httpx
import pytest

from app.core.llm import LLMClient
from app.deps import close_http_client, get_http_client, reset_http_client
from app.rag.embedder import Embedder


def test_get_http_client_returns_singleton():
    reset_http_client()
    client1 = get_http_client()
    client2 = get_http_client()
    assert client1 is client2
    assert not client1.is_closed
    reset_http_client()


def test_close_http_client_closes_and_cleans():
    reset_http_client()
    client = get_http_client()
    assert not client.is_closed
    asyncio.run(close_http_client())
    assert client.is_closed
    # 再次获取时重新生成有效客户端
    client_new = get_http_client()
    assert client_new is not client
    assert not client_new.is_closed
    asyncio.run(close_http_client())
    reset_http_client()


@pytest.mark.anyio
async def test_llm_client_reuses_injected_client():
    mock_client = httpx.AsyncClient()
    llm = LLMClient(
        base_url="http://mock.llm",
        api_key="mock-key",
        model="mock-model",
        client=mock_client,
    )
    assert llm._client is mock_client
    await mock_client.aclose()


@pytest.mark.anyio
async def test_embedder_reuses_injected_client():
    mock_client = httpx.AsyncClient()
    embedder = Embedder(
        base_url="http://mock.embed",
        api_key="mock-key",
        model="mock-model",
        client=mock_client,
    )
    assert embedder._client is mock_client
    await mock_client.aclose()
