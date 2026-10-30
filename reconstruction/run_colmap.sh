#!/usr/bin/env bash
# run_colmap.sh
# ─────────────────────────────────────────────────────────────────────────────
# Run COLMAP Structure-from-Motion pipeline on extracted frames.
# Outputs a sparse reconstruction to output/colmap/sparse/0/
#
# Prerequisites:
#   - COLMAP installed and on PATH (https://colmap.github.io/)
#   - Frames already extracted to output/frames/ (run extract_frames.py first)
#
# Usage:
#   bash run_colmap.sh [--gpu 0]
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

GPU_INDEX="${1:---gpu 0}"
FRAMES_DIR="output/frames"
COLMAP_DIR="output/colmap"
DATABASE="$COLMAP_DIR/database.db"
SPARSE_DIR="$COLMAP_DIR/sparse"

echo "═══════════════════════════════════════════════════════════"
echo "  COLMAP SfM Pipeline — Namma Space"
echo "═══════════════════════════════════════════════════════════"

# ── Sanity checks ────────────────────────────────────────────────────────────
if ! command -v colmap &>/dev/null; then
    echo "[ERROR] colmap not found on PATH. Install COLMAP first."
    exit 1
fi

if [ ! -d "$FRAMES_DIR" ] || [ -z "$(ls -A "$FRAMES_DIR" 2>/dev/null)" ]; then
    echo "[ERROR] No frames found in $FRAMES_DIR. Run extract_frames.py first."
    exit 1
fi

FRAME_COUNT=$(ls "$FRAMES_DIR"/*.jpg 2>/dev/null | wc -l | tr -d ' ')
echo "[INFO] Found $FRAME_COUNT frames in $FRAMES_DIR"

mkdir -p "$COLMAP_DIR" "$SPARSE_DIR"

# ── Step 1: Feature Extraction ───────────────────────────────────────────────
echo ""
echo "[STEP 1/3] Feature Extraction…"
colmap feature_extractor \
    --database_path "$DATABASE" \
    --image_path "$FRAMES_DIR" \
    --ImageReader.single_camera 1 \
    --ImageReader.camera_model SIMPLE_RADIAL \
    --SiftExtraction.use_gpu 1 \
    --SiftExtraction.gpu_index 0 \
    --SiftExtraction.max_num_features 8192

# ── Step 2: Feature Matching ─────────────────────────────────────────────────
echo ""
echo "[STEP 2/3] Sequential Feature Matching…"
colmap sequential_matcher \
    --database_path "$DATABASE" \
    --SiftMatching.use_gpu 1 \
    --SiftMatching.gpu_index 0 \
    --SequentialMatching.overlap 10 \
    --SequentialMatching.loop_detection 1

# ── Step 3: Sparse Reconstruction (Mapper) ───────────────────────────────────
echo ""
echo "[STEP 3/3] Mapper (Sparse Reconstruction)…"
colmap mapper \
    --database_path "$DATABASE" \
    --image_path "$FRAMES_DIR" \
    --output_path "$SPARSE_DIR" \
    --Mapper.num_threads 8 \
    --Mapper.init_min_tri_angle 4

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  COLMAP Done!"
echo "  Sparse model → $SPARSE_DIR/0/"
echo "  Next: bash run_nerfstudio.sh  OR  bash run_3dgs.sh"
echo "═══════════════════════════════════════════════════════════"
