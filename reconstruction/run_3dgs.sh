#!/usr/bin/env bash
# run_3dgs.sh
# ─────────────────────────────────────────────────────────────────────────────
# Train 3D Gaussian Splatting from COLMAP output.
#
# Prerequisites:
#   - gaussian-splatting repo cloned in the parent directory:
#       ../gaussian-splatting/   (relative to this reconstruction/ dir)
#   - COLMAP output at output/colmap/
#   - CUDA-capable GPU (RTX 4060 or better)
#   - gaussian-splatting Python environment activated
#
# Usage:
#   bash run_3dgs.sh [--iterations 30000]
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

ITERATIONS="${1:-30000}"
COLMAP_DIR="$(pwd)/output/colmap"
SPLAT_OUTPUT="$(pwd)/output/splat"
GS_REPO="../gaussian-splatting"

echo "═══════════════════════════════════════════════════════════"
echo "  3D Gaussian Splatting — Namma Space"
echo "═══════════════════════════════════════════════════════════"

# ── Sanity checks ────────────────────────────────────────────────────────────
if [ ! -d "$GS_REPO" ]; then
    echo "[ERROR] gaussian-splatting repo not found at $GS_REPO"
    echo "        Clone it: git clone https://github.com/graphdeco-inria/gaussian-splatting ../gaussian-splatting"
    exit 1
fi

if [ ! -d "$COLMAP_DIR/sparse/0" ]; then
    echo "[ERROR] COLMAP output not found at $COLMAP_DIR/sparse/0"
    echo "        Run run_colmap.sh first."
    exit 1
fi

mkdir -p "$SPLAT_OUTPUT"

# ── Training ─────────────────────────────────────────────────────────────────
echo ""
echo "[INFO] Training 3DGS for $ITERATIONS iterations…"
echo "[INFO] Source: $COLMAP_DIR"
echo "[INFO] Output: $SPLAT_OUTPUT"
echo ""

cd "$GS_REPO"
python train.py \
    -s "$COLMAP_DIR" \
    -m "$SPLAT_OUTPUT" \
    --iterations "$ITERATIONS" \
    --save_iterations 7000 15000 30000 \
    --checkpoint_iterations 15000 30000 \
    --densify_until_iter 15000

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  3DGS Training Done!"
echo "  Splat model → $SPLAT_OUTPUT/point_cloud/iteration_$ITERATIONS/"
echo "  Next: python export_web.py"
echo "═══════════════════════════════════════════════════════════"
