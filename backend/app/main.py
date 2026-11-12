"""FastAPI 应用入口。

启动：`uvicorn app.main:app --reload --port 8000`（在 backend 目录下）
接口文档：http://localhost:8000/docs

启动时自动从磁盘恢复已上传的文档（持久化，重启不丢）。
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import auth, chat, documents, health
from app.config import get_settings
from app.core.observability import setup_logging
from app.storage.workspace import WorkspaceRegistry

settings = get_settings()
setup_logging()  # 结构化日志：控制台 + logs/app.log


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """账号首次访问时恢复对应的文档快照。"""
    yield
    from app.deps import close_http_client

    await close_http_client()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        description="智能知识库问答与 Agent 助手平台（RAG 全链路）",
        version=settings.app_version,
        lifespan=lifespan,
    )
    app.state.workspaces = WorkspaceRegistry()

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
    app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
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
