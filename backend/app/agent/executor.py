"""Agent 执行器：Function Calling 循环（阶段 2 落地）。

流程：
1. 把 messages + 工具 schema 发给 LLM（流式）；
2. 若模型请求调用工具：解析参数 → 执行 handler（支持同步/异步）→
   结果回填为 role=tool 消息（按 OpenAI 协议，需先回填携带 tool_calls 的 assistant 消息）；
3. 重复直到模型不再调用工具，或达到最大轮数（agent_max_turns）；
4. 全程透传 delta；额外产出 tool_result 事件，供前端展示"Agent 做了什么"。

安全设计（面试可讲）：
- max_turns 硬上限：防止"模型反复调用工具"造成死循环与费用失控；
- 工具 handler 在注册时人工审核；参数按 JSON Schema 解析并做类型检查；
- 工具结果截断后回填（2000 字符），避免上下文爆炸。

事件协议：
- {"type": "delta", "content": ...}          文本增量
- {"type": "tool_result", "name": ..., "result": ...}  一次工具调用及其结果
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

from app.agent.tools import Tool, get_tool
from app.core.llm import LLMClient

_MAX_TOOL_RESULT = 2000  # 回填给 LLM 的结果上限
_MAX_TOOL_RESULT_LOG = 500  # 透传给前端的展示上限


class AgentExecutor:
    def __init__(self, llm: LLMClient, max_turns: int = 5):
        self.llm = llm
        self.max_turns = max_turns

    async def run(
        self, messages: list[dict], tools: list[Tool] | None = None
    ) -> AsyncIterator[dict]:
        """执行 Agent 循环，逐条产出 delta / tool_result 事件。"""
        schemas = [t.to_schema() for t in tools] if tools else None

        for _ in range(self.max_turns):
            content_parts: list[str] = []
            # 聚合分片 tool_call：同一 index 表示同一次调用（流式分多次下发）
            pending: dict[int, dict] = {}

            async for event in self.llm.stream_chat(messages, tools=schemas):
                etype = event["type"]
                if etype == "delta":
                    content_parts.append(event["content"])
                    yield {"type": "delta", "content": event["content"]}
                elif etype == "tool_call":
                    tc = event["tool_call"]
                    idx = tc.get("index", 0)
                    slot = pending.setdefault(idx, {"id": "", "name": "", "arguments": ""})
                    if tc.get("id"):
                        slot["id"] = tc["id"]
                    fn = tc.get("function") or {}
                    if fn.get("name"):
                        slot["name"] = fn["name"]
                    if fn.get("arguments"):
                        slot["arguments"] += fn["arguments"]

            # 模型没有请求工具：本轮就是最终回答
            if not pending:
                return

            # 回填携带 tool_calls 的 assistant 消息（OpenAI 协议要求）
            calls = [pending[i] for i in sorted(pending)]
            resolved = []
            for i, c in enumerate(calls):
                resolved.append({"id": c["id"] or f"call_{i}", "name": c["name"], "arguments": c["arguments"]})
            messages.append(
                {
                    "role": "assistant",
                    "content": "".join(content_parts) or None,
                    "tool_calls": [
                        {
                            "id": rc["id"],
                            "type": "function",
                            "function": {"name": rc["name"], "arguments": rc["arguments"]},
                        }
                        for rc in resolved
                    ],
                }
            )

            # 执行工具并回填结果
            for rc in resolved:
                result = await self._invoke(rc["name"], rc["arguments"])
                messages.append(
                    {"role": "tool", "tool_call_id": rc["id"], "content": result[:_MAX_TOOL_RESULT]}
                )
                yield {"type": "tool_result", "name": rc["name"], "result": result[:_MAX_TOOL_RESULT_LOG]}

        # 达到轮数上限仍未结束
        yield {
            "type": "delta",
            "content": "\n\n> ⚠️ 已达到工具调用次数上限，我将基于已有信息回答。",
        }

    async def _invoke(self, name: str, arguments: str) -> str:
        tool = get_tool(name)
        if tool is None:
            return f"错误：未知工具「{name}」"
        try:
            args = json.loads(arguments) if arguments else {}
            if not isinstance(args, dict):
                raise TypeError("工具参数必须是 JSON 对象")
            res = tool.handler(**args)
            if hasattr(res, "__await__"):
                res = await res
            return str(res)
        except Exception as exc:  # noqa: BLE001 —— 工具异常要回传 LLM 而非中断对话
            return f"错误：{exc}"
