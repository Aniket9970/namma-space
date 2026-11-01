@echo off
REM ─────────────────────────────────────────────────────────────────
REM  run_colmap.bat — Step B of the Namma Space pipeline
REM  Double-click this file OR run it from Command Prompt
REM ─────────────────────────────────────────────────────────────────

echo.
echo ===================================================
echo   COLMAP — Figuring out camera positions...
echo   This will take 5-20 minutes. Please wait!
echo ===================================================
echo.

REM Check COLMAP is installed
where colmap >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] COLMAP not found!
    echo Please make sure COLMAP is installed and added to PATH.
    echo Ask Antigravity for help if you are unsure.
    pause
    exit /b 1
)

REM Check frames exist
if not exist "output\frames\" (
    echo [ERROR] No frames folder found!
    echo Please run Step A first: python extract_frames.py ...
    pause
    exit /b 1
)

mkdir output\colmap 2>nul
mkdir output\colmap\sparse 2>nul

echo [Step 1/3] Extracting features from photos...
colmap feature_extractor ^
    --database_path output\colmap\database.db ^
    --image_path output\frames ^
    --ImageReader.single_camera 1 ^
    --ImageReader.camera_model SIMPLE_RADIAL ^
    --SiftExtraction.use_gpu 1 ^
    --SiftExtraction.gpu_index 0 ^
    --SiftExtraction.max_num_features 8192

echo.
echo [Step 2/3] Matching features between photos...
colmap sequential_matcher ^
    --database_path output\colmap\database.db ^
    --SiftMatching.use_gpu 1 ^
    --SiftMatching.gpu_index 0 ^
    --SequentialMatching.overlap 10 ^
    --SequentialMatching.loop_detection 1

echo.
echo [Step 3/3] Building sparse 3D map...
colmap mapper ^
    --database_path output\colmap\database.db ^
    --image_path output\frames ^
    --output_path output\colmap\sparse ^
    --Mapper.num_threads 8 ^
    --Mapper.init_min_tri_angle 4

echo.
echo ===================================================
echo   Done! COLMAP finished successfully.
echo   Now run Step C: run_nerfstudio.bat
echo ===================================================
pause
