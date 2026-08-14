"""Agent 工具注册框架。

设计：每个工具是一个 Tool 对象（name + description + parameters JSON Schema + handler）。
- LLM 通过 Function Calling 决定调用哪个工具、传什么参数；
- 执行器（executor.py）负责：调用 handler → 把结果回填给 LLM → 继续生成；
- handler 支持同步与异步两种写法；
- 安全：每次对话限制工具调用次数（agent_max_turns），防止死循环。

内置工具（阶段 2 落地）：
- calculator：安全四则运算（参数白名单正则校验）
- wiki_search：维基百科搜索（免费 API、无需 Key），展示"联网获取实时信息"能力
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

TOOL_REGISTRY: dict[str, Tool] = {}


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict  # JSON Schema
    handler: Callable[..., Any]

    def to_schema(self) -> dict:
        """转成 OpenAI tools 参数格式。"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


def register(tool: Tool) -> None:
    TOOL_REGISTRY[tool.name] = tool


def get_tool(name: str) -> Tool | None:
    return TOOL_REGISTRY.get(name)


def list_tool_schemas() -> list[dict]:
    """给 LLM 看的 tools 参数格式（兼容旧调用）。"""
    return [t.to_schema() for t in TOOL_REGISTRY.values()]


# ---- 工具 1：计算器（安全起见只允许数字、运算符、括号）----
_CALC_SAFE = re.compile(r"^[\d\s+\-*/().,]+$")


def _calc(expression: str) -> str:
    if not _CALC_SAFE.match(expression):
        return "错误：表达式包含非法字符"
    try:
        # eval 经过白名单校验，仅用于简单四则运算；后续可换 ast 解析更安全
        return str(eval(expression))
    except Exception as exc:  # noqa: BLE001
        return f"错误：{exc}"


register(
    Tool(
        name="calculator",
        description="计算数学表达式，如 '(1+2)*3'",
        parameters={
            "type": "object",
            "properties": {"expression": {"type": "string", "description": "数学表达式"}},
            "required": ["expression"],
        },
        handler=_calc,
    )
)


# ---- 工具 2：维基百科搜索（免费 API，无需 Key）----
_TAG_RE = re.compile(r"<[^>]+>")
_WIKI_HOSTS = [
    "https://zh.wikipedia.org/w/api.php",  # 中文优先
    "https://en.wikipedia.org/w/api.php",  # 主站备用（网络受限环境兜底）
]


def format_wiki_hits(hits: list[dict], limit: int) -> str:
    """把维基搜索结果格式化为给 LLM 的文本（去 HTML 标签）。纯函数便于测试。"""
    if not hits:
        return "没有找到相关条目"
    lines = []
    for i, hit in enumerate(hits[: int(limit)], 1):
        snippet = _TAG_RE.sub("", hit.get("snippet", "")).strip()
        lines.append(f"{i}. {hit['title']}：{snippet}")
    return "\n".join(lines)


async def _wiki_search(query: str, limit: int = 3) -> str:
    """调用维基百科搜索 API（多节点容错），返回标题 + 摘要片段。

    错误处理：可读的中文错误信息（而不是空字符串），超时自动切换备用节点。
    """
    import httpx

    params = {
        "action": "query",
        "list": "search",
        "srsearch": query,
        "srlimit": min(int(limit), 5),
        "format": "json",
        "utf8": 1,
    }
    last_error = "维基百科暂时无法访问"
    for host in _WIKI_HOSTS:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(host, params=params)
                resp.raise_for_status()
                data = resp.json()
            hits = data.get("query", {}).get("search", [])
            return format_wiki_hits(hits, limit)
        except httpx.HTTPStatusError as exc:
            return f"错误：维基百科接口返回状态码 {exc.response.status_code}"
        except httpx.TimeoutException:
            last_error = "维基百科连接超时，已尝试备用节点"
        except httpx.HTTPError as exc:
            last_error = f"网络错误：{exc}"
    return f"错误：{last_error}"


register(
    Tool(
        name="wiki_search",
        description="搜索维基百科获取实时信息，用于回答知识库之外的事实性问题",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键词"},
                "limit": {"type": "integer", "description": "返回条数，默认 3，最大 5"},
            },
            "required": ["query"],
        },
        handler=_wiki_search,
    )
)
