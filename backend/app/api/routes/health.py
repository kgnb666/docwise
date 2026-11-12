"""健康检查：验证服务存活 + 系统状态概览（运维/演示用）。"""

from fastapi import APIRouter

from app.config import get_settings
from app.core import utils

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    settings = get_settings()
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": settings.app_version,
        "config": {
            "llm_model": settings.llm_model,
            "embedding_provider": settings.embedding_provider,
            "embedding_model": settings.embedding_model,
            "tokenizer": utils.current_tokenizer_mode(),
            "agent_enabled": settings.agent_enabled,
        },
    }
