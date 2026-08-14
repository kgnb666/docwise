"""追问改写：把"指代不清"的追问扩展成自包含的检索查询。

面试高频题："连续追问怎么办？"
- 用户的追问常含指代词（它 / 这个 / 上面 / 刚才…），单独检索会跑偏；
- 方案：检测到追问时，用最近一轮用户问题做上文，拼接成扩展查询再检索；
- 阶段 2.5 可换成 LLM 改写（更准），接口保持 `rewrite_for_retrieval` 不变。
"""

from __future__ import annotations

# 常见指代/衔接词，命中任一即视为追问
_FOLLOWUP_HINTS = (
    "它", "它们", "这个", "这些", "那个", "那些",
    "上面", "上述", "刚才", "之前", "其", "该", "如上",
)


def is_follow_up(query: str) -> bool:
    """判断是否是追问（含指代词或过短）。"""
    if any(h in query for h in _FOLLOWUP_HINTS):
        return True
    return len(query.strip()) <= 4


def rewrite_for_retrieval(query: str, history: list[dict]) -> str:
    """把追问改写成自包含的检索查询。

    history 形如 [{"role": "user"|"assistant", "content": "..."}]。
    规则：取最近一条 user 问题作为上文，拼接当前追问；
    非追问或没有历史时原样返回。
    """
    if not history:
        return query
    last_user = ""
    for msg in reversed(history):
        if msg.get("role") == "user":
            last_user = msg.get("content", "")
            break
    if not last_user or not is_follow_up(query):
        return query
    return f"{last_user} {query}"
