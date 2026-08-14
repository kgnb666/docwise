# DocWise 一键全量验证（投递前跑这一个就行）
# 用法：powershell -ExecutionPolicy Bypass -File scripts/run_all.ps1
# 内容：静态检查 → 单元测试 → 真实检索评测(top-1) → 生成质量评测 → 基准 → 总结
# 注意：需要 backend/.env 已配置 API Key（后三步调用真实接口，总花费约 ¥1-2）

$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location "$Root\backend"
$py = "$PWD\.venv\Scripts\python.exe"

# 统一 UTF-8 输出：避免中文 Windows 控制台（GBK）打印 ¥ 等符号时崩溃
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"

Write-Host "`n== [1/6] Ruff 静态检查 ==" -ForegroundColor Cyan
& $py -m ruff check app tests scripts
Write-Host "`n== [2/6] 单元测试 ==" -ForegroundColor Cyan
& $py -m pytest -q -p no:cacheprovider

Write-Host "`n== [3/6] 真实检索评测（top-1 严格模式）==" -ForegroundColor Cyan
& $py scripts\run_eval.py --embedding openai --tokenizer jieba --reranker-api --top-k 1

Write-Host "`n== [4/6] 生成质量评测（DeepSeek 判分）==" -ForegroundColor Cyan
& $py scripts\run_eval_quality.py

Write-Host "`n== [5/6] 延迟/成本基准 ==" -ForegroundColor Cyan
& $py scripts\benchmark.py

Write-Host "`n== [6/6] 生成总结报告 ==" -ForegroundColor Cyan
& $py scripts\summarize_eval.py

Write-Host "`n✅ 全量验证完成！总结见 docs\eval\SUMMARY.md" -ForegroundColor Green
