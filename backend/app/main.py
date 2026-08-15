"""FastAPI 应用入口。

启动：`uvicorn app.main:app --reload --port 8000`（在 backend 目录下）
接口文档：http://localhost:8000/docs

启动时自动从磁盘恢复已上传的文档（持久化，重启不丢）。
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import chat, documents, health
from app.config import get_settings
from app.core.observability import log_event, setup_logging
from app.storage.document_store import get_document_store
from app.storage.persistence import restore_to_stores
from app.storage.vector_store import get_vector_store

settings = get_settings()
setup_logging()  # 结构化日志：控制台 + logs/app.log


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """启动：把磁盘上的文档快照恢复到内存存储（幂等，零 API 调用）。"""
    restored = restore_to_stores(get_vector_store(), get_document_store())
    if restored:
        log_event("restore", documents=restored)
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        description="智能知识库问答与 Agent 助手平台（RAG 全链路）",
        version="0.2.0",
        lifespan=lifespan,
    )

    # CORS：允许前端 dev server 跨域访问
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 注册路由
    app.include_router(health.router, prefix="/api")
    app.include_router(documents.router, prefix="/api/documents", tags=["documents"])
    app.include_router(chat.router, prefix="/api", tags=["chat"])

    @app.get("/")
    async def root() -> dict:
        return {
            "name": settings.app_name,
            "message": "DocWise API is running",
            "docs": "/docs",
            "health": "/api/health",
        }

    return app


app = create_app()
