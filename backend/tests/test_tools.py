import httpx
import pytest

from app.agent.tools import _calc, _wiki_search, format_wiki_hits, get_tool


def test_format_wiki_hits_strips_html_and_numbers():
    hits = [
        {"title": "检索增强生成", "snippet": "RAG 是 <span>一种</span> 架构"},
        {"title": "大语言模型", "snippet": "LLM"},
    ]
    out = format_wiki_hits(hits, 2)
    assert "1. 检索增强生成" in out
    assert "2. 大语言模型" in out
    assert "<span>" not in out  # HTML 标签已剥离


def test_format_wiki_hits_empty():
    assert format_wiki_hits([], 3) == "没有找到相关条目"


def test_format_wiki_hits_respects_limit():
    hits = [{"title": f"条目{i}", "snippet": "x"} for i in range(5)]
    out = format_wiki_hits(hits, 2)
    assert "3. 条目" not in out
    assert "2. 条目1" in out


def test_calc_normal_arithmetic():
    assert _calc("(1 + 2) * 3") == "9"
    assert _calc("10 / 2") == "5.0"
    assert _calc("100 - 50 + 25") == "75"


def test_calc_blocks_power_dos():
    assert _calc("9**9**9") == "错误：不支持幂运算"
    assert _calc("2**10") == "错误：不支持幂运算"
    assert "错误" in _calc("2^8")


def test_calc_blocks_illegal_characters_and_builtins():
    assert "错误" in _calc("__import__('os')")
    assert "错误" in _calc("open('/etc/passwd')")
    assert "错误" in _calc("eval('1+1')")


def test_calculator_registered_in_tool_registry():
    tool = get_tool("calculator")
    assert tool is not None
    assert tool.handler("(2+3)*4") == "20"


@pytest.mark.anyio
async def test_wiki_search_with_custom_client():
    mock_json = {
        "query": {
            "search": [
                {"title": "检索增强生成", "snippet": "知识库问答技术"}
            ]
        }
    }

    def handler(request: httpx.Request):
        return httpx.Response(200, json=mock_json)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        res = await _wiki_search("RAG", limit=1, client=client)
        assert "1. 检索增强生成：知识库问答技术" in res


@pytest.mark.anyio
async def test_wiki_search_timeout_fallback():
    call_hosts = []

    def handler(request: httpx.Request):
        call_hosts.append(str(request.url.host))
        if "zh.wikipedia.org" in str(request.url.host):
            raise httpx.TimeoutException("zh connection timeout")
        return httpx.Response(
            200,
            json={"query": {"search": [{"title": "RAG", "snippet": "Retrieval-Augmented Generation"}]}},
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        res = await _wiki_search("RAG", limit=1, client=client)
        assert "1. RAG：Retrieval-Augmented Generation" in res
        assert "zh.wikipedia.org" in call_hosts
        assert "en.wikipedia.org" in call_hosts

