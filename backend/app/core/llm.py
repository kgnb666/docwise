"""LLM 客户端：封装 OpenAI 兼容 /chat/completions 的流式调用。

为什么用 OpenAI 兼容格式？因为 DeepSeek / 通义千问 / Kimi / 本地 Ollama
都提供兼容接口，换模型只改 .env，不改代码。
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

import httpx


class LLMClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        temperature: float = 0.2,
        max_tokens: int = 1024,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    async def complete(self, messages: list[dict]) -> str:
        """非流式补全：聚合流式结果为完整文本。

        用于评测（LLM-as-Judge）等需要完整输出的场景。
        """
        parts: list[str] = []
        async for event in self.stream_chat(messages):
            if event["type"] == "delta":
                parts.append(event["content"])
        return "".join(parts)

    async def stream_chat(
        self, messages: list[dict], tools: list[dict] | None = None
    ) -> AsyncIterator[dict]:
        """流式对话。逐条产出增量消息。

        产出两种事件：
        - {"type": "delta", "content": str}         普通文本增量
        - {"type": "tool_call", ...}                 模型请求调用工具（阶段 2）
        """
        if not self.api_key:
            raise RuntimeError("未配置 OPENAI_API_KEY，请先在 backend/.env 中填写")

        payload: dict = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stream": True,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        async with httpx.AsyncClient(timeout=120) as client, client.stream(
            "POST",
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json=payload,
        ) as resp:
            resp.raise_for_status()
            # 逐行解析 SSE：data: {...}
            async for line in resp.aiter_lines():
                line = line.strip()
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    obj = json.loads(data)
                except ValueError:
                    continue
                choices = obj.get("choices") or []
                if not choices:
                    continue
                delta = choices[0].get("delta") or {}
                if delta.get("content"):
                    yield {"type": "delta", "content": delta["content"]}
                if delta.get("tool_calls"):
                    for tc in delta["tool_calls"]:
                        yield {"type": "tool_call", "tool_call": tc}
