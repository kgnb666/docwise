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


def test_markdown_heading_aware_chunking_inheritance():
    doc = """# 核心设计
这是核心设计的介绍。

## 混合检索
混合检索结合了 BM25 和向量。

### Rerank 精排
重排是精细打分。

## 向量存储
存储采用内存实现。
"""
    chunks = make_chunks(doc, doc_id="doc-1", doc_name="arch.md")
    assert len(chunks) == 4

    assert chunks[0].text.startswith("[核心设计]\n")
    assert chunks[0].metadata["heading_path"] == "核心设计"
    assert chunks[0].metadata["headings"] == ["核心设计"]

    assert chunks[1].text.startswith("[核心设计 > 混合检索]\n")
    assert chunks[1].metadata["heading_path"] == "核心设计 > 混合检索"

    assert chunks[2].text.startswith("[核心设计 > 混合检索 > Rerank 精排]\n")
    assert chunks[2].metadata["heading_path"] == "核心设计 > 混合检索 > Rerank 精排"

    assert chunks[3].text.startswith("[核心设计 > 向量存储]\n")
    assert chunks[3].metadata["heading_path"] == "核心设计 > 向量存储"


def test_markdown_heading_ignores_code_block_comments():
    doc = """# 代码演示
下面是一段代码：

```python
# 这只是代码注释，绝不是标题
x = 1
```

这是代码后的总结。
"""
    chunks = make_chunks(doc, doc_id="doc-2", doc_name="code.md")
    assert len(chunks) == 1
    assert chunks[0].metadata["heading_path"] == "代码演示"
    assert "这只是代码注释" in chunks[0].text
    assert "# 这只是代码注释" not in chunks[0].metadata["heading_path"]

