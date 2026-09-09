"""聊天接口：非流式（测试/兜底）+ 流式 SSE（前端主用）。

工程化：
- 限流：按 IP 令牌桶，防止 LLM Key 被刷爆（429）；
- 埋点：结构化日志记录每次问答的关键信息（query / 耗时 / 引用数）。
"""

from __future__ import annotations

import json
import time

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.config import get_settings
from app.core.observability import log_event, new_query_id, truncate
from app.core.rate_limit import RateLimiter
from app.core.utils import estimate_tokens
from app.deps import get_pipeline, get_rate_limiter
from app.rag.pipeline import RagPipeline

router = APIRouter()

_settings = get_settings()


class ChatRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000, description="用户问题")
    history: list[dict] = Field(default_factory=list, description="历史消息 [{role, content}]")


def get_client_ip(request: Request) -> str:
    """提取客户端真实 IP：优先从 X-Forwarded-For 获取，次选 X-Real-IP，最后回退至 client.host。"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        first_ip = forwarded.split(",")[0].strip()
        if first_ip:
            return first_ip
    real_ip = request.headers.get("X-Real-IP")
    if real_ip and real_ip.strip():
        return real_ip.strip()
    return request.client.host if request.client else "unknown"


def enforce_rate_limit(
    request: Request, limiter: RateLimiter = Depends(get_rate_limiter)
) -> None:
    """按客户端真实 IP 做令牌桶限流。"""
    if not _settings.rate_limit_enabled:
        return
    key = get_client_ip(request)
    if not limiter.allow(key):
        raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试")


@router.post("/chat", dependencies=[Depends(enforce_rate_limit)])
async def chat(req: ChatRequest, pipeline: RagPipeline = Depends(get_pipeline)) -> dict:
    """非流式问答（便于测试与调试）。"""
    t0 = time.perf_counter()
    query_id = new_query_id()
    try:
        result = await pipeline.chat(req.query, req.history, query_id=query_id)
        est_input = estimate_tokens(req.query) + sum(
            estimate_tokens(c.get("text", "")) for c in result["citations"]
        ) + sum(estimate_tokens(str(h.get("content", ""))) for h in req.history)
        log_event(
            "chat",
            query_id=query_id,
            query=truncate(req.query),
            chunks=len(result["citations"]),
            tools=len(result.get("tools", [])),
            latency_ms=round((time.perf_counter() - t0) * 1000, 1),
            est_input_tokens=est_input,
            est_output_tokens=estimate_tokens(result.get("answer", "")),
        )
        return result
    except Exception as exc:
        log_event(
            "chat_error",
            query_id=query_id,
            query=truncate(req.query),
            error=truncate(str(exc), 500),
        )
        raise HTTPException(status_code=502, detail=f"生成失败：{exc}") from exc


@router.post("/chat/stream", dependencies=[Depends(enforce_rate_limit)])
async def chat_stream(req: ChatRequest, pipeline: RagPipeline = Depends(get_pipeline)):
    """流式问答（SSE）。前端解析事件：query_rewritten / citations / delta / tool_result / done。"""
    t0 = time.perf_counter()
    query_id = new_query_id()
    citations: list[dict] = []
    answer_chars = 0

    async def gen():
        nonlocal citations, answer_chars
        try:
            async for event in pipeline.stream_answer(
                req.query, req.history, query_id=query_id
            ):
                if event["type"] == "citations":
                    citations = event["citations"]
                elif event["type"] == "delta":
                    answer_chars += len(event["content"])
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            est_input = estimate_tokens(req.query) + sum(
                estimate_tokens(c.get("text", "")) for c in citations
            ) + sum(estimate_tokens(str(h.get("content", ""))) for h in req.history)
            log_event(
                "chat_stream",
                query_id=query_id,
                query=truncate(req.query),
                chunks=len(citations),
                latency_ms=round((time.perf_counter() - t0) * 1000, 1),
                est_input_tokens=est_input,
                est_output_tokens=estimate_tokens("x" * answer_chars),  # 仅用长度估算，不缓存全文
            )
        except Exception as exc:  # noqa: BLE001 —— 流中断线也要给前端明确的错误事件
            log_event(
                "chat_stream_error",
                query_id=query_id,
                query=truncate(req.query),
                error=truncate(str(exc), 500),
            )
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)}, ensure_ascii=False)}\n\n"
        finally:
            yield "data: [DONE]\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")
