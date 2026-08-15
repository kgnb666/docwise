@echo off
REM ===== DocWise 本地部署模式（生产构建 + 预览，模拟线上）=====
REM 双击本文件：先构建前端，再启动后端 + 生产预览
REM 启动后浏览器访问 http://localhost:4173

echo [1/3] 构建前端（生产模式）...
cd /d %~dp0frontend
call npm run build
if errorlevel 1 (
    echo 构建失败，请先运行 npm install
    pause
    exit /b 1
)

echo [2/3] 启动后端...
start "DocWise Backend" cmd /k "cd /d %~dp0backend && .venv\Scripts\uvicorn app.main:app --host 0.0.0.0 --port 8000"

echo [3/3] 启动前端生产预览...
start "DocWise Frontend Preview" cmd /k "cd /d %~dp0frontend && npm run preview -- --port 4173"

echo.
echo ============================================
echo  前端页面:     http://localhost:4173
echo  后端接口文档: http://localhost:8000/docs
echo  停止: 直接关闭两个黑色窗口即可
echo ============================================
echo.
pause
