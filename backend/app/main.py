"""FastAPI 应用入口。

启动：`uvicorn app.main:app --reload --port 8000`（在 backend 目录下）
接口文档：http://localhost:8000/docs
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import chat, documents, health
from app.config import get_settings
from app.core.observability import setup_logging

settings = get_settings()
setup_logging()  # 结构化日志：控制台 + logs/app.log


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        description="智能知识库问答与 Agent 助手平台（RAG 全链路）",
        version="0.1.0",
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
