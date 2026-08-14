"""分词器测试：legacy 行为 + jieba 模式切换与回退。"""

from app.core import utils


def _reset_mode():
    utils.set_tokenizer_mode("legacy")


def test_legacy_chinese_bigrams():
    _reset_mode()
    tokens = utils.tokenize("机器学习很好")
    assert "机器" in tokens
    assert "学习" in tokens
    assert "很好" in tokens


def test_legacy_english_lowercase():
    _reset_mode()
    tokens = utils.tokenize("Hello World Hello")
    assert tokens.count("hello") == 2
    assert "world" in tokens


def test_jieba_mode_when_available():
    _reset_mode()
    try:
        utils.set_tokenizer_mode("jieba")
        tokens = utils.tokenize("机器学习是人工智能的分支")
        # jieba 会把完整词切开：机器/学习/人工智能
        assert "机器" in tokens
        assert "学习" in tokens
        assert "人工智能" in tokens
    finally:
        _reset_mode()


def test_auto_falls_back_to_legacy_without_jieba():
    _reset_mode()
    utils._jieba = False  # 模拟 jieba 不可用
    try:
        utils.set_tokenizer_mode("auto")
        tokens = utils.tokenize("自然语言处理")
        # legacy：单字 + 二元组
        assert "自然" in tokens
        assert "语言" in tokens
    finally:
        utils._jieba = None
        _reset_mode()


def test_invalid_mode_rejected():
    _reset_mode()
    try:
        utils.set_tokenizer_mode("nonsense")
        assert False, "应当抛出 ValueError"
    except ValueError:
        pass
