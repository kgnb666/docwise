"""Agent 执行器测试：用假 LLM 脚本化流式事件，验证 Function Calling 循环。

不需要真实 API：FakeLLM 按调用次数返回预置事件序列。
"""

import asyncio

from app.agent.executor import AgentExecutor
from app.agent.tools import TOOL_REGISTRY, Tool, register


class FakeLLM:
    """按调用次数返回预置的事件序列（最后一组重复使用）。"""

    def __init__(self, turns: list[list[dict]]):
        self.turns = turns
        self.calls = 0

    async def stream_chat(self, messages, tools=None):
        events = self.turns[min(self.calls, len(self.turns) - 1)]
        self.calls += 1
        for e in events:
            yield e


def _tool_call(name: str, args: str, call_id: str = "call_1") -> dict:
    return {
        "type": "tool_call",
        "tool_call": {
            "index": 0,
            "id": call_id,
            "function": {"name": name, "arguments": args},
        },
    }


def _run(executor: AgentExecutor, messages: list[dict] | None = None) -> list[dict]:
    """异步生成器需要先异步收集，asyncio.run 不能直接跑 async generator。"""

    async def collect() -> list[dict]:
        out: list[dict] = []
        async for ev in executor.run(messages or [], list(TOOL_REGISTRY.values())):
            out.append(ev)
        return out

    return asyncio.run(collect())


def test_single_tool_call_then_answer():
    llm = FakeLLM(
        [
            [_tool_call("calculator", '{"expression": "1+2"}')],
            [{"type": "delta", "content": "结果是 3"}],
        ]
    )
    ex = AgentExecutor(llm, max_turns=5)
    events = _run(ex)

    tool_results = [e for e in events if e["type"] == "tool_result"]
    assert len(tool_results) == 1
    assert tool_results[0]["name"] == "calculator"
    assert "3" in tool_results[0]["result"]
    deltas = [e["content"] for e in events if e["type"] == "delta"]
    assert deltas == ["结果是 3"]
    # 第一轮调工具，第二轮正常回答
    assert llm.calls == 2


def test_unknown_tool_returns_error_to_llm():
    llm = FakeLLM(
        [
            [_tool_call("no_such_tool", "{}")],
            [{"type": "delta", "content": "抱歉，我无法完成"}],
        ]
    )
    ex = AgentExecutor(llm, max_turns=5)
    events = _run(ex)
    tr = next(e for e in events if e["type"] == "tool_result")
    assert "未知工具" in tr["result"]


def test_max_turns_prevents_infinite_loop():
    # 模型每次都请求调用工具 → 应在 max_turns 后强制结束
    llm = FakeLLM([[_tool_call("calculator", '{"expression": "1"}')]])
    ex = AgentExecutor(llm, max_turns=3)
    events = _run(ex)
    assert llm.calls == 3
    assert any("次数上限" in e.get("content", "") for e in events if e["type"] == "delta")


def test_async_handler_is_awaited():
    async def slow_double(x: int) -> str:
        return f"got {x * 2}"

    register(
        Tool(
            name="double",
            description="翻倍",
            parameters={
                "type": "object",
                "properties": {"x": {"type": "integer"}},
                "required": ["x"],
            },
            handler=slow_double,
        )
    )
    try:
        llm = FakeLLM(
            [
                [_tool_call("double", '{"x": 21}')],
                [{"type": "delta", "content": "ok"}],
            ]
        )
        ex = AgentExecutor(llm, max_turns=5)
        events = _run(ex)
        tr = next(e for e in events if e["type"] == "tool_result")
        assert tr["result"] == "got 42"
    finally:
        TOOL_REGISTRY.pop("double", None)
