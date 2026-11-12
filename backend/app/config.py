"""应用配置：所有环境变量集中管理。

用法：`from app.config import get_settings`，然后 `settings.xxx`。
修改配置只改 .env，不改代码。
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # 服务
    app_name: str = "DocWise"
    app_version: str = "0.2.0"
    host: str = "0.0.0.0"
    port: int = 8000
    # 持久化数据目录（文档快照；可被 DATA_DIR 环境变量覆盖，测试隔离用）
    data_dir: str = "data"
    auth_cookie_secure: bool = True
    auth_session_seconds: int = Field(default=86400, gt=0)

    # LLM（OpenAI 兼容接口）
    openai_base_url: str = "https://api.openai.com/v1"
    openai_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"
    # 嵌入接口可独立配置（例如 DeepSeek 无嵌入 API，可用硅基流动的 bge-m3）
    # 留空则复用 openai_base_url / openai_api_key
    embedding_base_url: str = ""
    embedding_api_key: str = ""
    # 嵌入实现：openai（真实接口）| hash（离线哈希，无需 Key，供测试/CI/原型）
    embedding_provider: str = "openai"
    # 单次向云端 /embeddings 接口批量发送的最大分块数（防 400/413 报错）
    embedding_batch_size: int = 32
    temperature: float = 0.2
    max_tokens: int = 1024

    # 检索参数
    top_k: int = 5
    rerank_top_k: int = 3
    chunk_size: int = 800
    chunk_overlap: int = 100
    # 混合检索权重：0~1，越大越偏向关键词（BM25）
    hybrid_alpha: float = 0.4
    # Rerank：null（不重排）| overlap（轻量重叠精排，MVP，默认离线）| api（云端 bge-reranker）
    reranker: str = "overlap"
    rerank_alpha: float = 0.3
    # Rerank API 可独立配置（例如硅基流动 /v1）；留空则依次回退 embedding_base_url/embedding_api_key、
    # 再回退 openai_base_url/openai_api_key（参考 embedder 的写法）
    rerank_base_url: str = ""
    rerank_api_key: str = ""
    rerank_model: str = "BAAI/bge-reranker-v2-m3"
    # 云端 rerank 一次精排的候选数（应 >= rerank_top_k；最终仍按 rerank_top_k 截断返回）
    rerank_top_n: int = 3
    # 相关度阈值：低于该分数的检索结果视为"未命中"（触发兜底）。
    # 真实嵌入（bge-m3）下相关块 ≈ 0.7、无关 ≈ 0.1，取 0.3；离线哈希嵌入请保持 0.0
    score_threshold: float = 0.0

    # Agent 工具调用
    agent_enabled: bool = True
    agent_max_turns: int = 5

    # 追问改写
    query_rewrite_enabled: bool = True

    # 知识库未命中时的兜底模式：
    # strict —— 只答知识库（防幻觉人设）；chat —— 允许模型用常识/联网工具回答
    fallback_mode: str = "chat"

    # 检索结果缓存（热点问答跳过 embedding 调用）
    retrieval_cache_enabled: bool = True
    retrieval_cache_ttl: int = 300

    # 限流（按 IP 令牌桶）
    rate_limit_enabled: bool = True
    rate_limit_capacity: float = 20.0
    rate_limit_refill_per_sec: float = 1.0

    # CORS 白名单（前端 dev server 地址；env 中是 JSON 数组字符串）
    cors_origins: list[str] = ["http://localhost:5173"]


@lru_cache
def get_settings() -> Settings:
    """缓存 Settings 实例，避免每次请求都重新读 env。"""
    return Settings()
