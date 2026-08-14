"""健康检查：验证服务存活 + 系统状态概览（运维/演示用）。"""

from fastapi import APIRouter

from app.config import get_settings
from app.core import utils
from app.storage.document_store import get_document_store
from app.storage.vector_store import get_vector_store

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    settings = get_settings()
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": "0.1.0",
        "stats": {
            "documents": get_document_store().count(),
            "chunks": get_vector_store().count(),
        },
        "config": {
            "llm_model": settings.llm_model,
            "embedding_provider": settings.embedding_provider,
            "embedding_model": settings.embedding_model,
            "tokenizer": utils.current_tokenizer_mode(),
            "agent_enabled": settings.agent_enabled,
        },
    }
