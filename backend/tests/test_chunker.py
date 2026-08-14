"""分块器与分词器测试。"""

from app.core.utils import tokenize
from app.rag.chunker import make_chunks, split_text


def test_split_short_text_single_chunk():
    chunks = split_text("你好世界", chunk_size=800, overlap=100)
    assert chunks == ["你好世界"]


def test_split_long_text_respects_chunk_size():
    text = "段落一。" * 200  # 600 字符，单段超过 chunk_size
    chunks = split_text(text, chunk_size=100, overlap=20)
    assert len(chunks) > 1
    assert all(len(c) <= 100 for c in chunks)


def test_split_paragraph_aggregation():
    text = "第一段。\n第二段。\n第三段。"
    chunks = split_text(text, chunk_size=100, overlap=0)
    # 每段都很短，应聚合为一块
    assert len(chunks) == 1
    assert "第三段" in chunks[0]


def test_make_chunks_metadata():
    chunks = make_chunks("内容一\n内容二", doc_id="abc", doc_name="test.md")
    assert all(c.doc_id == "abc" for c in chunks)
    assert all(c.doc_name == "test.md" for c in chunks)
    assert [c.index for c in chunks] == list(range(len(chunks)))


def test_tokenize_chinese_bigrams():
    tokens = tokenize("机器学习很好")
    # 包含单字和相邻二元组
    assert "机器" in tokens
    assert "学习" in tokens
    assert "很好" in tokens


def test_tokenize_english_lowercase():
    tokens = tokenize("Hello World Hello")
    assert tokens.count("hello") == 2
    assert "world" in tokens
