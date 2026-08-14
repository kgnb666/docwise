"""测试共享夹具。

关键：在导入任何 app 模块之前，先屏蔽真实 .env 里的 Key——
保证测试 100% 离线、确定性（不产生真实 API 调用、不消耗余额）。
pydantic-settings 的优先级：环境变量 > .env 文件，因此这里设置环境变量即可覆盖。

另外每个测试默认使用 legacy 分词，保证确定性（jieba 行为由 test_tokenizer.py 单独验证）。
"""

import os

os.environ["OPENAI_API_KEY"] = ""
os.environ["EMBEDDING_API_KEY"] = ""
os.environ["EMBEDDING_PROVIDER"] = "hash"

import pytest

from app.core import utils


@pytest.fixture(autouse=True)
def _legacy_tokenizer():
    utils.set_tokenizer_mode("legacy")
    yield
    utils.set_tokenizer_mode("legacy")
