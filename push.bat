@echo off
REM ===== DocWise: Push to GitHub =====
REM Double-click to push all local commits to GitHub.
REM First time: a browser window opens asking you to sign in to GitHub.
REM After that, pushing is automatic.
chcp 65001 >nul

cd /d %~dp0

echo.
echo Pushing to github.com/kgnb666/docwise ...
echo If a browser window opens, sign in to GitHub and authorize.
echo.
git push

echo.
if errorlevel 1 (
    echo PUSH FAILED. See the message above.
) else (
    echo PUSH OK. All commits are now on GitHub.
)
echo.
pause
