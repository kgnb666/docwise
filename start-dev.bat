@echo off
REM ===== DocWise Quick Start (Dev Mode) =====
REM Double-click to start backend + frontend in two windows
REM Then open http://localhost:5173
chcp 65001 >nul

echo Starting DocWise (Dev Mode)...

REM Backend (FastAPI, port 8000)
start "DocWise Backend" cmd /k "cd /d %~dp0backend && .venv\Scripts\uvicorn app.main:app --reload --port 8000"

REM Frontend (Vite, port 5173, /api proxied to backend)
start "DocWise Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"

echo.
echo ============================================
echo   API Docs : http://localhost:8000/docs
echo   Web UI   : http://localhost:5173
echo   Stop     : close the two black windows
echo ============================================
echo.
pause
