"""RAG 主流程：查询改写 → 检索（带缓存）→ 组装 Prompt → 流式生成（可带 Agent 工具调用）→ 引用溯源。

事件协议（SSE 输出给前端）：
- {"type": "query_rewritten", "original": "...", "rewritten": "..."}  追问被改写（可选）
- {"type": "citations", "citations": [{doc_name, text, score, ...}]}
- {"type": "delta", "content": "..."}
- {"type": "tool_result", "name": "...", "result": "..."}   Agent 调用了工具
- {"type": "done"}
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from app.agent.executor import AgentExecutor
from app.agent.tools import TOOL_REGISTRY
from app.config import Settings
from app.core.cache import Cache
from app.core.llm import LLMClient
from app.rag.embedder import Embedder
from app.rag.query_rewrite import rewrite_for_retrieval
from app.rag.retriever import RetrievedChunk, Retriever

_SYSTEM_PROMPT = """你是「DocWise」智能知识库助手，负责基于提供的资料回答问题。

规则：
1. 只依据参考资料回答；资料中没有的信息，明确说"资料中没有相关内容"，绝不编造。
2. 引用来源时用 [1]、[2] 标注，编号对应参考资料列表。
3. 回答用中文，简洁、有条理，可用 Markdown。
"""


def build_messages(
    query: str, chunks: list[RetrievedChunk], history: list[dict]
) -> list[dict]:
    """组装 Prompt：参考资料 + 历史对话 + 当前问题。"""
    refs = "\n\n".join(
        f"[{i + 1}] 来源《{c.doc_name}》片段{c.index}：\n{c.text}"
        for i, c in enumerate(chunks)
    )
    user_content = (
        f"参考资料：\n{refs}\n\n历史对话：\n{history}\n\n问题：{query}"
        if history
        else f"参考资料：\n{refs}\n\n问题：{query}"
    )
    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


class RagPipeline:
    def __init__(
        self,
        embedder: Embedder,
        retriever: Retriever,
        settings: Settings,
        retrieval_cache: Cache | None = None,
        citation_preview_len: int = 200,
    ):
        self.embedder = embedder
        self.retriever = retriever
        self.settings = settings
        self.retrieval_cache = retrieval_cache
        # 引用预览截断长度：前端展示用 200；评测需完整上下文（如 2000）
        self.citation_preview_len = citation_preview_len
        self.llm = LLMClient(
            base_url=settings.openai_base_url,
            api_key=settings.openai_api_key,
            model=settings.llm_model,
            temperature=settings.temperature,
            max_tokens=settings.max_tokens,
        )
        self.agent = AgentExecutor(self.llm, max_turns=settings.agent_max_turns)

    async def _retrieve(self, query: str) -> list[RetrievedChunk]:
        """检索（带缓存）：热点问题命中缓存后跳过 embedding 调用。"""
        if self.retrieval_cache is not None:
            hit = self.retrieval_cache.get(query)
            if hit is not None:
                return hit
        vectors = await self.embedder.embed([query])
        chunks = self.retriever.retrieve(query, vectors[0])
        if self.retrieval_cache is not None and chunks:
            self.retrieval_cache.set(query, chunks)
        return chunks

    def _citations(self, chunks: list[RetrievedChunk]) -> list[dict]:
        return [
            {
                "chunk_id": c.chunk_id,
                "doc_id": c.doc_id,
                "doc_name": c.doc_name,
                "index": c.index,
                "score": round(c.score, 4),
                "text": c.text[: self.citation_preview_len],  # 引用预览截断（评测时传大值拿全文）
            }
            for c in chunks
        ]

    async def stream_answer(
        self, query: str, history: list[dict] | None = None
    ) -> AsyncIterator[dict]:
        """一次完整问答，产出 query_rewritten → citations → delta*/tool_result* → done。"""
        history = history or []

        # 0) 追问改写（把指代不清的追问扩展成自包含查询）
        retrieval_query = query
        if self.settings.query_rewrite_enabled:
            retrieval_query = rewrite_for_retrieval(query, history)
            if retrieval_query != query:
                yield {"type": "query_rewritten", "original": query, "rewritten": retrieval_query}

        # 1) 检索（带缓存）
        chunks = await self._retrieve(retrieval_query)
        yield {"type": "citations", "citations": self._citations(chunks)}

        # 3) 无资料时的兜底提示（面试可讲：显式处理"知识库外问题"）
        if not chunks:
            yield {
                "type": "delta",
                "content": "抱歉，知识库中还没有相关内容。请先上传文档，或换个问法试试。",
            }
            yield {"type": "done"}
            return

        # 4) 组装 Prompt 并流式生成（Agent 启用时走工具调用闭环）
        messages = build_messages(retrieval_query, chunks, history)
        if self.settings.agent_enabled and TOOL_REGISTRY:
            async for event in self.agent.run(messages, tools=list(TOOL_REGISTRY.values())):
                yield event
        else:
            async for event in self.llm.stream_chat(messages):
                yield event
        yield {"type": "done"}

    async def chat(self, query: str, history: list[dict] | None = None) -> dict:
        """非流式问答（用于测试与兜底）：聚合流式结果为完整回答。"""
        answer_parts: list[str] = []
        citations: list[dict] = []
        tools_used: list[dict] = []
        async for event in self.stream_answer(query, history):
            if event["type"] == "citations":
                citations = event["citations"]
            elif event["type"] == "delta":
                answer_parts.append(event["content"])
            elif event["type"] == "tool_result":
                tools_used.append({"name": event["name"], "result": event["result"]})
        return {"answer": "".join(answer_parts), "citations": citations, "tools": tools_used}
