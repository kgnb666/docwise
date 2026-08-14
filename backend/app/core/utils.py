"""通用工具：中英文分词（接口不变，两套实现可切换）。

- legacy（零依赖）：英文按词 + 中文按「单字 + 相邻二元组」；
- jieba（推荐）：真实中文分词，对长文本/复杂语料更准；
  未安装 jieba 时自动回退 legacy（auto 模式）。

配置：TOKENIZER=auto|legacy|jieba（.env 或环境变量），测试可用 set_tokenizer_mode() 切换。
"""

from __future__ import annotations

import os
import re
from itertools import pairwise

# 中文字符（含扩展区）
_CJK_RE = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]")
# 英文 / 数字 / 下划线组成的词
_WORD_RE = re.compile(r"[a-zA-Z0-9_]+")

_TOKENIZER_MODE = os.environ.get("TOKENIZER", "auto").strip().lower()

_jieba = None  # None=未加载, False=不可用, 模块=已加载


def set_tokenizer_mode(mode: str) -> None:
    """测试用：切换分词实现（legacy / jieba / auto）。"""
    global _TOKENIZER_MODE
    mode = mode.strip().lower()
    if mode not in ("auto", "legacy", "jieba"):
        raise ValueError(f"未知分词模式：{mode}")
    _TOKENIZER_MODE = mode


def current_tokenizer_mode() -> str:
    """当前生效的分词模式（auto 时按是否可用解析为实际实现）。"""
    if _TOKENIZER_MODE == "auto":
        return "jieba" if _load_jieba() else "legacy"
    return _TOKENIZER_MODE


def _load_jieba():
    global _jieba
    if _jieba is None:
        try:
            import jieba  # noqa: F401

            _jieba = True
        except ImportError:
            _jieba = False
    return _jieba


def _legacy_tokenize(text: str) -> list[str]:
    """零依赖分词：英文单词（小写）+ 中文单字与相邻二元组。"""
    tokens: list[str] = []
    for m in _WORD_RE.finditer(text):
        tokens.append(m.group(0).lower())
    cjk_chars = _CJK_RE.findall(text)
    tokens.extend(cjk_chars)
    tokens.extend(a + b for a, b in pairwise(cjk_chars))
    return tokens


def tokenize(text: str) -> list[str]:
    """统一分词入口：BM25 / 哈希嵌入 / Rerank 都走这里。"""
    if _TOKENIZER_MODE in ("jieba", "auto") and _load_jieba():
        import jieba

        return [t.strip().lower() for t in jieba.cut(text) if t.strip()]
    return _legacy_tokenize(text)
