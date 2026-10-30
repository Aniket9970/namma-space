@echo off
REM ─────────────────────────────────────────────────────────────────
REM  run_3dgs.bat — Step C Part 2 of the Namma Space pipeline
REM  Double-click this file OR run it from Command Prompt
REM ─────────────────────────────────────────────────────────────────

echo.
echo ===================================================
echo   3D Gaussian Splatting — Making it look pretty!
echo   This will take 20-40 minutes. Almost there!
echo ===================================================
echo.

REM Check COLMAP output exists
if not exist "output\colmap\sparse\0\" (
    echo [ERROR] COLMAP output not found!
    echo Please run Step B first: run_colmap.bat
    pause
    exit /b 1
)

REM Check gaussian-splatting repo exists
if not exist "..\gaussian-splatting\train.py" (
    echo [ERROR] gaussian-splatting folder not found!
    echo.
    echo Please run this in Command Prompt:
    echo   git clone https://github.com/graphdeco-inria/gaussian-splatting ..\gaussian-splatting --recursive
    echo.
    echo Then run this file again.
    pause
    exit /b 1
)

mkdir output\splat 2>nul

echo [Running] 3D Gaussian Splatting training...
cd ..\gaussian-splatting
python train.py ^
    -s "%~dp0output\colmap" ^
    -m "%~dp0output\splat" ^
    --iterations 30000 ^
    --save_iterations 7000 15000 30000 ^
    --checkpoint_iterations 15000 30000 ^
    --densify_until_iter 15000

cd "%~dp0"

echo.
echo ===================================================
echo   Done! Gaussian Splatting finished.
echo   Now run Step D: python export_web.py
echo ===================================================
pause
