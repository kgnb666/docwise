@echo off
chcp 65001 >nul
echo ============================================
echo   DocWise deploy script - keep window open
echo ============================================
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0docwise-deploy.ps1"
echo.
echo Script finished. Press any key to close...
pause >nul
