"""结构化日志与埋点（MVP：JSON Lines → logs/app.log + 控制台）。

后续演进（面试可讲）：接 OpenTelemetry 做链路追踪，Prometheus 采集指标，
量化每次问答的延迟 / 成本 / 缓存命中率。
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
        }
        if hasattr(record, "event"):
            payload["event"] = record.event
        if hasattr(record, "fields"):
            payload.update(record.fields)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def setup_logging(log_dir: str | Path = "logs") -> None:
    """幂等初始化：控制台 + 文件（JSON Lines）。"""
    logger = logging.getLogger("docwise")
    if logger.handlers:  # 已初始化
        return
    logger.setLevel(logging.INFO)

    fmt = JsonFormatter()
    console = logging.StreamHandler()
    console.setFormatter(fmt)
    logger.addHandler(console)

    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(log_dir / "app.log", encoding="utf-8")
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)


def log_event(topic: str, **fields) -> None:
    """记一条结构化日志：log_event("chat", query="...", latency_ms=123)"""
    logging.getLogger("docwise").info(
        "event", extra={"event": topic, "fields": fields}
    )
