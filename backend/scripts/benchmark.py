"""基准测试：真实 API 延迟与成本估算（需要 Key）。

回答面试官高频问题：「你的系统一次问答多快、多少钱？」

用法（backend 目录）：
    .\\.venv\\Scripts\\python scripts\\benchmark.py

输出：docs/eval/benchmark.json + 控制台汇总。
口径说明：token 数按「字符数 / 1.5」粗估；价格是估算常量（见 report.pricing_note），
以各平台官网实时价格为准。
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# 控制台输出强制 UTF-8：防止中文 Windows（GBK）打印 ¥ 等符号崩溃
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:  # noqa: S110, BLE001 —— 尽力而为，不支持时保持默认编码
    pass

from app.config import get_settings
from app.deps import get_embedder, get_retriever
from app.rag.pipeline import RagPipeline
from scripts.run_eval_quality import seed_corpus

# 价格估算（¥ / 百万 token；以官网实时价为准）
PRICE_INPUT_PER_M = 2.0  # DeepSeek deepseek-chat 输入量级
PRICE_OUTPUT_PER_M = 8.0  # DeepSeek deepseek-chat 输出量级
PRICE_EMBED_PER_M = 0.8  # 硅基流动 bge-m3 嵌入量级

QUESTIONS = [
    "什么是RAG？",
    "git rebase 和 merge 有什么区别",
    "MySQL 为什么用 B+ 树做索引",
]


def estimate_tokens(text: str) -> int:
    """中英混合粗略估算：约 1.5 字符 ≈ 1 token。"""
    return max(1, int(len(text) / 1.5))


async def main() -> None:
    settings = get_settings()
    settings.agent_enabled = False  # 基准测 RAG 问答，不含 Agent 工具调用
    pipeline = RagPipeline(
        get_embedder(),
        get_retriever(),
        settings,
        retrieval_cache=None,
        citation_preview_len=2000,
    )
    n_chunks = await seed_corpus()

    # 1) 单次查询嵌入延迟
    t0 = time.perf_counter()
    await pipeline.embedder.embed(["测试查询"])
    embed_ms = (time.perf_counter() - t0) * 1000

    # 2) 完整问答延迟与成本估算
    items = []
    for q in QUESTIONS:
        t0 = time.perf_counter()
        result = await pipeline.chat(q, [])
        ms = (time.perf_counter() - t0) * 1000

        in_tokens = sum(estimate_tokens(c.get("text", "")) for c in result["citations"])
        out_tokens = estimate_tokens(result.get("answer", ""))
        cost = (in_tokens * PRICE_INPUT_PER_M + out_tokens * PRICE_OUTPUT_PER_M) / 1_000_000
        items.append(
            {
                "question": q,
                "latency_ms": round(ms, 1),
                "answer_chars": len(result.get("answer", "")),
                "est_input_tokens": in_tokens,
                "est_output_tokens": out_tokens,
                "est_cost_yuan": round(cost, 5),
            }
        )
        print(f"[{q}] {ms:.0f}ms | 答案{items[-1]['answer_chars']}字 | 约¥{cost:.5f}")

    avg_ms = sum(i["latency_ms"] for i in items) / len(items)
    avg_cost = sum(i["est_cost_yuan"] for i in items) / len(items)
    report = {
        "corpus_chunks": n_chunks,
        "embed_single_query_ms": round(embed_ms, 1),
        "chat_avg_latency_ms": round(avg_ms, 1),
        "chat_avg_cost_yuan": round(avg_cost, 6),
        "items": items,
        "pricing_note": (
            f"价格估算口径：输入 ¥{PRICE_INPUT_PER_M}/M token、输出 ¥{PRICE_OUTPUT_PER_M}/M、"
            f"嵌入 ¥{PRICE_EMBED_PER_M}/M（以官网实时价为准）；token 数按字符数/1.5 粗估。"
        ),
    }
    out = Path(__file__).resolve().parents[1].parent / "docs" / "eval" / "benchmark.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n平均延迟 {avg_ms:.0f}ms | 平均成本约 ¥{avg_cost:.5f}/次")
    print(f"写入：{out}")


if __name__ == "__main__":
    asyncio.run(main())
