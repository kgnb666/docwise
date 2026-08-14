"""追问改写测试。"""

from app.rag.query_rewrite import is_follow_up, rewrite_for_retrieval


def test_follow_up_detection():
    assert is_follow_up("它有哪些优点")
    assert is_follow_up("这个怎么实现")
    assert is_follow_up("上面说的对吗")
    assert not is_follow_up("什么是RAG")


def test_rewrite_uses_last_user_question():
    history = [
        {"role": "user", "content": "什么是RAG？"},
        {"role": "assistant", "content": "RAG 是检索增强生成……"},
    ]
    out = rewrite_for_retrieval("它有哪些优点", history)
    assert "什么是RAG" in out
    assert "它有哪些优点" in out


def test_no_rewrite_without_history():
    assert rewrite_for_retrieval("什么是RAG", []) == "什么是RAG"


def test_no_rewrite_for_standalone_question():
    history = [{"role": "user", "content": "什么是RAG？"}]
    assert rewrite_for_retrieval("Docker 怎么部署", history) == "Docker 怎么部署"
