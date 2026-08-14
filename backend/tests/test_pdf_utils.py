"""PDF 文本提取测试：用伪 pypdf 验证我们的拼接与空页处理逻辑。

真实 PDF 解析是 pypdf 的职责，这里只验证我们自己的集成逻辑。
"""

import sys

from app.core.pdf_utils import extract_pdf_text


class _FakePage:
    def __init__(self, text):
        self._text = text

    def extract_text(self):
        return self._text


class _FakePypdf:
    """伪造 pypdf 模块：PdfReader(raw) -> 带 pages 的 reader。"""

    def __init__(self, pages):
        self._pages = pages

    def PdfReader(self, *args, **kwargs):
        return type("FakeReader", (), {"pages": self._pages})()


def _patch_pypdf(monkeypatch, pages):
    monkeypatch.setitem(sys.modules, "pypdf", _FakePypdf(pages))


def test_concats_pages_with_newline(monkeypatch):
    _patch_pypdf(monkeypatch, [_FakePage("第一页内容"), _FakePage("第二页内容")])
    assert extract_pdf_text(b"whatever") == "第一页内容\n第二页内容"


def test_skips_empty_and_none_pages(monkeypatch):
    _patch_pypdf(monkeypatch, [_FakePage(""), _FakePage("有内容"), _FakePage(None)])
    assert extract_pdf_text(b"whatever") == "有内容"


def test_all_empty_returns_empty(monkeypatch):
    _patch_pypdf(monkeypatch, [_FakePage(""), _FakePage("   ")])
    assert extract_pdf_text(b"whatever") == ""
