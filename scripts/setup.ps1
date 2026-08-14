# DocWise 一键环境准备（Windows）
# 用法：powershell -ExecutionPolicy Bypass -File scripts/setup.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "==> [1/4] 准备 Python 虚拟环境" -ForegroundColor Cyan
# 优先使用 3.11~3.13；没有则退回默认 python
$python = $null
foreach ($cand in @("py -3.12", "py -3.11", "py -3.13", "python")) {
    try {
        & cmd /c "$cand --version 2>nul" | Out-Null
        if ($LASTEXITCODE -eq 0) { $python = $cand; break }
    } catch {}
}
if (-not $python) { Write-Host "未找到 Python，请先安装 Python 3.11+"; exit 1 }

Set-Location "$Root\backend"
if (-not (Test-Path .venv)) {
    if ($python -eq "python") { python -m venv .venv } else { & cmd /c "$python -m venv .venv" }
}
$venvPy = "$PWD\.venv\Scripts\python.exe"

Write-Host "==> [2/4] 安装后端依赖" -ForegroundColor Cyan
& $venvPy -m pip install --disable-pip-version-check -q --upgrade pip
& $venvPy -m pip install --disable-pip-version-check -q -r requirements.txt

Write-Host "==> [3/4] 生成 .env（如不存在）" -ForegroundColor Cyan
if (-not (Test-Path .env)) { Copy-Item .env.example .env }

Write-Host "==> [4/4] 安装前端依赖" -ForegroundColor Cyan
Set-Location "$Root\frontend"
if (-not (Test-Path node_modules)) { npm install }

Write-Host ""
Write-Host "✅ 环境准备完成！接下来：" -ForegroundColor Green
Write-Host "  1) 编辑 backend\.env，填入 OPENAI_API_KEY"
Write-Host "  2) 启动后端：  cd backend;  .\.venv\Scripts\uvicorn app.main:app --reload --port 8000"
Write-Host "  3) 启动前端：  cd frontend;  npm run dev"
Write-Host "  4) 浏览器打开 http://localhost:5173"
