#!/usr/bin/env bash
# run_nerfstudio.sh
# ─────────────────────────────────────────────────────────────────────────────
# Train a Nerfacto model with Nerfstudio and export a Poisson mesh.
#
# Prerequisites:
#   - Nerfstudio installed (pip install nerfstudio)
#   - COLMAP sparse model at output/colmap/sparse/0/
#   - run_colmap.sh already completed
#
# Usage:
#   bash run_nerfstudio.sh
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

COLMAP_DIR="output/colmap"
NERF_OUTPUT="output/nerf"
MESH_OUTPUT="output/mesh"

echo "═══════════════════════════════════════════════════════════"
echo "  Nerfstudio Training — Namma Space"
echo "═══════════════════════════════════════════════════════════"

# ── Sanity checks ────────────────────────────────────────────────────────────
if ! command -v ns-train &>/dev/null; then
    echo "[ERROR] ns-train not found. Install nerfstudio: pip install nerfstudio"
    exit 1
fi

if [ ! -d "$COLMAP_DIR/sparse/0" ]; then
    echo "[ERROR] COLMAP output not found at $COLMAP_DIR/sparse/0"
    echo "        Run run_colmap.sh first."
    exit 1
fi

mkdir -p "$NERF_OUTPUT" "$MESH_OUTPUT"

# ── Step 1: Process COLMAP data for Nerfstudio ───────────────────────────────
echo ""
echo "[STEP 1/3] Converting COLMAP data for Nerfstudio…"
ns-process-data images \
    --data "$COLMAP_DIR/../frames" \
    --output-dir "$NERF_OUTPUT/data" \
    --colmap-model-path "$COLMAP_DIR/sparse/0"

# ── Step 2: Train Nerfacto ───────────────────────────────────────────────────
echo ""
echo "[STEP 2/3] Training Nerfacto model…"
ns-train nerfacto \
    --data "$NERF_OUTPUT/data" \
    --output-dir "$NERF_OUTPUT/checkpoints" \
    --max-num-iterations 30000 \
    --pipeline.model.predict-normals True \
    --viewer.no-enable

# Find the latest checkpoint directory
LATEST_CKPT=$(find "$NERF_OUTPUT/checkpoints" -name "config.yml" | sort | tail -1 | xargs dirname)
echo "[INFO] Latest checkpoint: $LATEST_CKPT"

# ── Step 3: Export Poisson Mesh ──────────────────────────────────────────────
echo ""
echo "[STEP 3/3] Exporting Poisson mesh…"
ns-export poisson \
    --load-config "$LATEST_CKPT/config.yml" \
    --output-dir "$MESH_OUTPUT" \
    --target-num-faces 500000 \
    --num-pixels-per-side 2048

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  Nerfstudio Done!"
echo "  Mesh PLY → $MESH_OUTPUT/mesh.ply"
echo "  Next: python export_web.py"
echo "═══════════════════════════════════════════════════════════"
