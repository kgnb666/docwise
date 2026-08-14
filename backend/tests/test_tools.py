"""工具模块测试（纯函数部分，不依赖网络）。"""

from app.agent.tools import format_wiki_hits


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
