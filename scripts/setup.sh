#!/usr/bin/env bash
# DocWise 一键环境准备（macOS / Linux）
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "==> [1/4] 准备 Python 虚拟环境"
cd "$ROOT/backend"
PYTHON="${PYTHON:-python3}"
if ! command -v "$PYTHON" >/dev/null; then
  echo "未找到 python3，请先安装 Python 3.11+"
  exit 1
fi
"$PYTHON" -m venv .venv
source .venv/bin/activate

echo "==> [2/4] 安装后端依赖"
pip install --disable-pip-version-check -q --upgrade pip
pip install --disable-pip-version-check -q -r requirements.txt

echo "==> [3/4] 生成 .env（如不存在）"
[ -f .env ] || cp .env.example .env

echo "==> [4/4] 安装前端依赖"
cd "$ROOT/frontend"
[ -d node_modules ] || npm install

echo ""
echo "✅ 环境准备完成！"
echo "  1) 编辑 backend/.env，填入 OPENAI_API_KEY"
echo "  2) 启动后端：cd backend && source .venv/bin/activate && uvicorn app.main:app --reload --port 8000"
echo "  3) 启动前端：cd frontend && npm run dev"
echo "  4) 打开 http://localhost:5173"
