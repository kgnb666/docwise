@echo off
REM ===== DocWise Quick Start (Production Preview Mode) =====
REM Double-click to build frontend, then start backend + preview
REM Then open http://localhost:4173
chcp 65001 >nul

echo [1/3] Building frontend (production)...
cd /d %~dp0frontend
call npm run build
if errorlevel 1 (
    echo Build failed. Please run: npm install
    pause
    exit /b 1
)

echo [2/3] Starting backend...
start "DocWise Backend" cmd /k "cd /d %~dp0backend && .venv\Scripts\uvicorn app.main:app --host 0.0.0.0 --port 8000"

echo [3/3] Starting frontend preview...
start "DocWise Frontend Preview" cmd /k "cd /d %~dp0frontend && npm run preview -- --port 4173"

echo.
echo ============================================
echo   Web UI   : http://localhost:4173
echo   API Docs : http://localhost:8000/docs
echo   Stop     : close the two black windows
echo ============================================
echo.
pause
