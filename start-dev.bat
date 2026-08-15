@echo off
REM ===== DocWise 一键启动（开发模式）=====
REM 双击本文件：自动打开后端 + 前端两个终端窗口
REM 启动后浏览器访问 http://localhost:5173

echo 正在启动 DocWise...

REM 启动后端（FastAPI，端口 8000）
start "DocWise Backend" cmd /k "cd /d %~dp0backend && .venv\Scripts\uvicorn app.main:app --reload --port 8000"

REM 启动前端（Vite，端口 5173，/api 自动代理到后端）
start "DocWise Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"

echo.
echo ============================================
echo  后端接口文档: http://localhost:8000/docs
echo  前端页面:     http://localhost:5173
echo  停止: 直接关闭两个黑色窗口即可
echo ============================================
echo.
pause
