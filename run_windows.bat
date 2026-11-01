@echo off
REM ─────────────────────────────────────────────────────────────
REM Namma Space — One-Click Windows Launcher
REM Double-click this file to start both backend & web viewer!
REM ─────────────────────────────────────────────────────────────

cd /d "%~dp0"
title Namma Space Launcher

echo.
echo ==========================================================
echo   Namma Space — Indoor Spatial Digital Twin Engine
echo   Launching on Windows...
echo ==========================================================
echo.

where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python was not found in PATH!
    pause
    exit /b 1
)

where npm >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] npm was not found in PATH!
    pause
    exit /b 1
)

echo [1/3] Checking dependencies...
python -m pip install -q -r backend\requirements.txt
if not exist "frontend\node_modules" (
    echo First-time setup: Installing frontend dependencies...
    cd frontend && npm install && cd ..
)

echo [2/3] Launching FastAPI Backend...
start "Namma Space Backend (port 8000)" cmd /c "cd backend && python -m uvicorn main:app --host 127.0.0.1 --port 8000"

timeout /t 2 >nul

echo [3/3] Launching Vite Frontend...
start "Namma Space Frontend (port 5173)" cmd /c "cd frontend && npm run dev"

timeout /t 2 >nul

echo [OK] Opening browser...
start http://localhost:5173/

echo.
echo ==========================================================
echo   Namma Space is running!
echo   Web Viewer: http://localhost:5173/
echo ==========================================================
echo.
pause
