"""把三份评测报告合并成一份可读总结：docs/eval/SUMMARY.md。

用法（backend 目录）：
    python scripts/summarize_eval.py

读取：docs/eval/offline_report.json / quality_report.json / benchmark.json
输出：docs/eval/SUMMARY.md（README 可直接引用）
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

DOCS_EVAL = Path(__file__).resolve().parents[1].parent / "docs" / "eval"


def _load(name: str) -> dict:
    path = DOCS_EVAL / name
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def render() -> str:
    offline = _load("offline_report.json")
    quality = _load("quality_report.json")
    bench = _load("benchmark.json")

    lines = ["# DocWise 评测总结（自动生成）", ""]
    lines.append(f"> 生成时间：{time.strftime('%Y-%m-%d %H:%M')}")
    lines.append("")

    # 1) 检索命中率
    lines.append("## 检索命中率（真实 embedding）")
    if offline.get("modes"):
        lines.append("")
        lines.append("| 配置 | 命中 | 准确率 |")
        lines.append("|---|---|---|")
        for m in offline["modes"]:
            lines.append(f"| {m['name']} | {m['hits']}/{m['total']} | {m['accuracy']:.1%} |")
        lines.append("")
        lines.append(f"- 语料：{offline.get('corpus_chunks', '?')} 块 | 测试集：{offline.get('test_set', '')} | top-k={offline.get('top_k')} | 分词：{offline.get('tokenizer', '?')}")
    else:
        lines.append("\n（未生成，先运行 scripts/run_eval.py）")
    lines.append("")

    # 2) 生成质量
    lines.append("## 生成质量（LLM-as-Judge）")
    if quality.get("count"):
        lines.append("")
        lines.append(f"- 引用命中 recall：**{quality.get('recall', 0):.1%}**")
        lines.append(f"- 忠实度 faithfulness：**{quality.get('avg_faithfulness', 0):.2f}**")
        lines.append(f"- 相关性 relevance：**{quality.get('avg_relevance', 0):.2f}**")
    else:
        lines.append("\n（未生成，先运行 scripts/run_eval_quality.py）")
    lines.append("")

    # 3) 基准
    lines.append("## 基准（延迟 / 成本）")
    if bench.get("chat_avg_latency_ms"):
        lines.append("")
        lines.append(f"- 单次问答平均延迟：**{bench['chat_avg_latency_ms']:.0f}ms**")
        lines.append(f"- 单次问答平均成本：**约 ¥{bench['chat_avg_cost_yuan']:.5f}**")
        lines.append(f"- 单次查询嵌入：{bench.get('embed_single_query_ms', '?')}ms")
        lines.append(f"- {bench.get('pricing_note', '')}")
    else:
        lines.append("\n（未生成，先运行 scripts/benchmark.py）")
    lines.append("")

    return "\n".join(lines)


def main() -> None:
    text = render()
    out = DOCS_EVAL / "SUMMARY.md"
    out.write_text(text, encoding="utf-8")
    print(f"已生成：{out}")


if __name__ == "__main__":
    main()
