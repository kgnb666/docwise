"""生成质量评测：系统作答 + LLM-as-Judge 打分（需要 API Key）。

指标：recall（引用命中率）、faithfulness（忠实度）、answer_relevance（相关性）。
与 scripts/run_eval.py（离线检索命中率）互补：一个测"检得准不准"，一个测"答得好不好"。

用法（backend 目录）：
    .\\.venv\\Scripts\\python scripts\\run_eval_quality.py
    .\\.venv\\Scripts\\python scripts\\run_eval_quality.py --test-set tests/data/test_set.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings
from app.core.llm import LLMClient
from app.deps import get_embedder, get_retriever
from app.eval.judge import LLMJudge
from app.eval.runner import run_quality_eval
from app.rag.chunker import make_chunks
from app.rag.pipeline import RagPipeline
from app.storage.vector_store import get_vector_store

BACKEND_DIR = Path(__file__).resolve().parents[1]
SAMPLES_DIR = BACKEND_DIR / "samples"
DEFAULT_TEST_SET = BACKEND_DIR / "tests" / "data" / "test_set.json"
DEFAULT_OUT = BACKEND_DIR.parent / "docs" / "eval" / "quality_report.json"


async def seed_corpus() -> int:
    """评测前置：把 samples/*.md 分块向量化后写入全局向量库。"""
    embedder = get_embedder()
    store = get_vector_store()
    store.clear()
    total = 0
    for f in sorted(SAMPLES_DIR.glob("*.md")):
        text = f.read_text(encoding="utf-8")
        chunks = make_chunks(text, doc_id=f.stem, doc_name=f.name)
        vectors = await embedder.embed([c.text for c in chunks])
        for chunk, vec in zip(chunks, vectors):
            store.add(
                chunk.id,
                vec,
                {
                    "doc_id": chunk.doc_id,
                    "doc_name": chunk.doc_name,
                    "index": chunk.index,
                    "text": chunk.text,
                },
            )
        total += len(chunks)
    return total


def main() -> None:
    parser = argparse.ArgumentParser(description="DocWise 生成质量评测（LLM-as-Judge）")
    parser.add_argument("--test-set", default=str(DEFAULT_TEST_SET))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args()

    settings = get_settings()
    if not settings.openai_api_key:
        sys.exit("请先在 backend/.env 配置 OPENAI_API_KEY（DeepSeek/通义等兼容接口均可）")

    # 评测测的是 RAG 回答质量：禁用 Agent 工具调用，避免模型去调外部工具干扰打分
    settings.agent_enabled = False
    pipeline = RagPipeline(
        get_embedder(),
        get_retriever(),
        settings,
        retrieval_cache=None,
        citation_preview_len=2000,  # 评测需要完整片段作为判分上下文（前端预览仍为 200）
    )
    # Judge 用低温（0）保证打分稳定
    judge = LLMJudge(
        LLMClient(
            settings.openai_base_url,
            settings.openai_api_key,
            settings.llm_model,
            temperature=0,
        )
    )

    test_set = json.loads(Path(args.test_set).read_text(encoding="utf-8"))
    n_chunks = asyncio.run(seed_corpus())
    print(f"语料已入库：{n_chunks} 块 | 测试集：{len(test_set)} 条 | 每条 1 次作答 + 2 次判分，耗时会较久")
    report = run_quality_eval(pipeline, judge, test_set)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n===== 生成质量评测结果 =====")
    print(f"recall(引用命中)      = {report['recall']:.1%}")
    print(f"faithfulness(忠实度)  = {report['avg_faithfulness']:.2f}")
    print(f"relevance(相关性)     = {report['avg_relevance']:.2f}")
    print(f"\n报告已写入：{out}")


if __name__ == "__main__":
    main()
