"""检索离线评测：对比不同检索配置的命中率（无需 API Key）。

背景：RAG 系统的效果必须有数据支撑，这是本项目的差异化亮点之一。
本脚本在本地语料（backend/samples/*.md）上跑「纯向量 vs 混合检索」的
命中率对比，输出评测报告。Rerank 精排在接入后自动纳入对比。

用法（在 backend 目录下）：
    .\\.venv\\Scripts\\python scripts\\run_eval.py
    .\\.venv\\Scripts\\python scripts\\run_eval.py --embedding openai   # 需要 API Key
    .\\.venv\\Scripts\\python scripts\\run_eval.py --out docs/eval/offline_report.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

# 允许直接以脚本方式运行（python scripts/run_eval.py）
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core import utils as core_utils
from app.rag.chunker import make_chunks
from app.rag.embedder import Embedder
from app.rag.embedder_hash import HashEmbedder
from app.rag.reranker import APIReranker, NullReranker, OverlapReranker
from app.rag.retriever import Retriever
from app.storage.vector_store import InMemoryVectorStore

BACKEND_DIR = Path(__file__).resolve().parents[1]
SAMPLES_DIR = BACKEND_DIR / "samples"
DEFAULT_TEST_SET = BACKEND_DIR / "tests" / "data" / "test_set.json"
DEFAULT_OUT = BACKEND_DIR.parent / "docs" / "eval" / "offline_report.json"


async def build_corpus(embedder, chunk_size: int = 200, overlap: int = 50) -> InMemoryVectorStore:
    """把 samples 下的文档分块、向量化后写入全新的内存向量库。

    chunk_size 默认 200：示例文档较短，用大分块会导致每篇只有 1 块，
    检索退化为"二选一"，命中率指标失去区分度（评测第一课：语料要足够细）。
    """
    store = InMemoryVectorStore()
    for f in sorted(SAMPLES_DIR.glob("*.md")):
        if f.name == "README.md":  # 目录说明文档不算知识内容
            continue
        text = f.read_text(encoding="utf-8")
        chunks = make_chunks(text, doc_id=f.stem, doc_name=f.name, chunk_size=chunk_size, overlap=overlap)
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
    return store


async def run_mode(
    store, embedder, test_set: list[dict], alpha: float, reranker, top_k: int = 5
) -> dict:
    """以指定检索配置跑一遍测试集，返回命中率与明细。"""
    retriever = Retriever(store, top_k=top_k, rerank_top_k=3, alpha=alpha, reranker=reranker)
    hits = 0
    details = []
    for item in test_set:
        query = item["question"]
        qv = (await embedder.embed([query]))[0]
        results = retriever.retrieve(query, qv)
        top_docs = [r.doc_name for r in results]
        hit = item["expected_doc"] in top_docs
        hits += int(hit)
        details.append(
            {
                "question": query,
                "expected": item["expected_doc"],
                "top3": top_docs[:3],
                "hit": hit,
            }
        )
    return {
        "hits": hits,
        "total": len(test_set),
        "accuracy": round(hits / len(test_set), 4),
        "details": details,
    }


async def run_mode_api_rerank(
    store, embedder, test_set: list[dict], reranker, top_k: int = 5
) -> dict:
    """混合粗召回(top_k) → 云端 rerank API 精排(top_n) → 命中率。"""
    retriever = Retriever(store, top_k=top_k, rerank_top_k=top_k, alpha=0.4, reranker=NullReranker())
    hits = 0
    details = []
    for item in test_set:
        query = item["question"]
        qv = (await embedder.embed([query]))[0]
        results = retriever.retrieve(query, qv)
        results = await reranker.rerank(query, results)  # 云端交叉编码精排
        top_docs = [r.doc_name for r in results]
        hit = item["expected_doc"] in top_docs
        hits += int(hit)
        details.append(
            {
                "question": query,
                "expected": item["expected_doc"],
                "top3": top_docs[:3],
                "hit": hit,
            }
        )
    return {
        "hits": hits,
        "total": len(test_set),
        "accuracy": round(hits / len(test_set), 4),
        "details": details,
    }


async def run(args: argparse.Namespace) -> None:
    if args.embedding == "openai":
        from app.config import get_settings

        s = get_settings()
        embedder = Embedder(
            base_url=s.embedding_base_url or s.openai_base_url,
            api_key=s.embedding_api_key or s.openai_api_key,
            model=s.embedding_model,
        )
    else:
        embedder = HashEmbedder()

    test_set = json.loads(Path(args.test_set).read_text(encoding="utf-8"))
    store = await build_corpus(embedder, chunk_size=args.chunk_size, overlap=args.overlap)
    print(f"语料：{store.count()} 个文本块 | 测试集：{len(test_set)} 条")

    modes = [
        ("纯向量检索", await run_mode(store, embedder, test_set, alpha=0.0, reranker=NullReranker(), top_k=args.top_k)),
        ("混合检索", await run_mode(store, embedder, test_set, alpha=0.4, reranker=NullReranker(), top_k=args.top_k)),
        ("混合+OverlapRerank", await run_mode(store, embedder, test_set, alpha=0.4, reranker=OverlapReranker(alpha=0.3), top_k=args.top_k)),
    ]
    if args.reranker_api:
        from app.config import get_settings

        s = get_settings()
        api_reranker = APIReranker(
            base_url=s.embedding_base_url or s.openai_base_url,
            api_key=s.embedding_api_key or s.openai_api_key,
        )
        modes.append(
            ("混合+bge-reranker(API)", await run_mode_api_rerank(store, embedder, test_set, api_reranker, top_k=args.top_k))
        )

    report = {
        "embedding": args.embedding,
        "tokenizer": core_utils.current_tokenizer_mode(),
        "reranker_api": args.reranker_api,
        "test_set": args.test_set,
        "corpus_chunks": store.count(),
        "chunk_size": args.chunk_size,
        "top_k": args.top_k,
        "modes": [{"name": name, **data} for name, data in modes],
        "note": (
            "命中率 = 期望来源文档出现在 top-k 检索结果中的比例。"
            "说明：离线哈希嵌入下向量与关键词信号高度重合，各模式分数接近属正常现象；"
            "真实 embedding 与 bge-reranker 下对比更有区分度。"
        ),
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n===== 评测结果 =====")
    for name, data in modes:
        print(f"{name:<24} 命中 {data['hits']}/{data['total']}  准确率 {data['accuracy']:.1%}")
    print(f"\n报告已写入：{out}")


def main() -> None:
    parser = argparse.ArgumentParser(description="DocWise 离线检索评测")
    parser.add_argument("--embedding", choices=["hash", "openai"], default="hash")
    parser.add_argument("--test-set", default=str(DEFAULT_TEST_SET))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--chunk-size", type=int, default=200)
    parser.add_argument("--overlap", type=int, default=50)
    parser.add_argument(
        "--tokenizer", choices=["auto", "legacy", "jieba"], default=None,
        help="分词实现（默认沿用环境配置 TOKENIZER）",
    )
    parser.add_argument(
        "--reranker-api", action="store_true",
        help="额外对比云端 bge-reranker API（需配置嵌入 API Key）",
    )
    args = parser.parse_args()

    if args.tokenizer:
        from app.core import utils

        utils.set_tokenizer_mode(args.tokenizer)
        print(f"分词模式：{args.tokenizer}")
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
