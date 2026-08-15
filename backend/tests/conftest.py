"""测试共享夹具。

关键：在导入任何 app 模块之前，先屏蔽真实 .env 里的 Key——
保证测试 100% 离线、确定性（不产生真实 API 调用、不消耗余额）。
pydantic-settings 的优先级：环境变量 > .env 文件，因此这里设置环境变量即可覆盖。

另外每个测试默认使用 legacy 分词，保证确定性（jieba 行为由 test_tokenizer.py 单独验证）。
"""

import os
import tempfile

os.environ["OPENAI_API_KEY"] = ""
os.environ["EMBEDDING_API_KEY"] = ""
os.environ["EMBEDDING_PROVIDER"] = "hash"
# 兜底模式锁定 strict：离线测试不触发真实 LLM 调用
os.environ["FALLBACK_MODE"] = "strict"
# 相关度阈值归零：离线哈希嵌入分数整体偏低，避免被 .env 的真实阈值误过滤
os.environ["SCORE_THRESHOLD"] = "0"
# 数据目录隔离：测试不写真实 data/（持久化快照落到临时目录）
os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="docwise-test-")

import pytest

from app.core import utils


@pytest.fixture(autouse=True)
def _legacy_tokenizer():
    utils.set_tokenizer_mode("legacy")
    yield
    utils.set_tokenizer_mode("legacy")
