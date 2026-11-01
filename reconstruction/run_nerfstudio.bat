@echo off
REM ─────────────────────────────────────────────────────────────────
REM  run_nerfstudio.bat — Step C Part 1 of the Namma Space pipeline
REM  Double-click this file OR run it from Command Prompt
REM ─────────────────────────────────────────────────────────────────

echo.
echo ===================================================
echo   Nerfstudio — Building the 3D mesh...
echo   This will take 30-60 minutes. Go grab a coffee!
echo ===================================================
echo.

REM Check nerfstudio is installed
where ns-train >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Nerfstudio not found!
    echo Please run: pip install nerfstudio
    echo Ask Antigravity for help if you see errors.
    pause
    exit /b 1
)

REM Check COLMAP output exists
if not exist "output\colmap\sparse\0\" (
    echo [ERROR] COLMAP output not found!
    echo Please run Step B first: run_colmap.bat
    pause
    exit /b 1
)

mkdir output\nerf 2>nul
mkdir output\mesh 2>nul

echo [Step 1/3] Converting photos for Nerfstudio...
ns-process-data images ^
    --data output\frames ^
    --output-dir output\nerf\data ^
    --colmap-model-path output\colmap\sparse\0

echo.
echo [Step 2/3] Training the 3D model (this is the slow part)...
ns-train nerfacto ^
    --data output\nerf\data ^
    --output-dir output\nerf\checkpoints ^
    --max-num-iterations 30000 ^
    --pipeline.model.predict-normals True ^
    --viewer.no-enable

echo.
echo [Step 3/3] Exporting mesh...

REM Find latest checkpoint config
for /f "delims=" %%i in ('dir /b /s /a-d output\nerf\checkpoints\*\config.yml 2^>nul ^| sort /r') do (
    set LATEST_CONFIG=%%i
    goto :found_config
)
:found_config

ns-export poisson ^
    --load-config "%LATEST_CONFIG%" ^
    --output-dir output\mesh ^
    --target-num-faces 500000 ^
    --num-pixels-per-side 2048

echo.
echo ===================================================
echo   Done! Nerfstudio finished.
echo   Now run Step C Part 2: run_3dgs.bat
echo ===================================================
pause
