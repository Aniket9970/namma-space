# Namma Space — Indoor Spatial Engine
> **Techfest IIT Bombay 2026-27 | Hybrid 3D Navigation & Reconstruction**

Namma Space transforms ordinary smartphone videos or photos of indoor venues into a zero-install, responsive 3D web application where remote users walk around in first person, search POIs (e.g. "Meeting Room 4", "3-seater sofas"), and follow obstacle-aware walking paths computed on a floor-aligned navmesh.

---

## 3-Layer Hybrid Architecture

1. **Visual Layer**: Crisp 360 equirectangular panorama nodes (`4096x2048` production, `1024` LOD for fast loading).
2. **Geometry Layer**: Low-poly proxy mesh (`mesh/proxy.glb`, $< 50\text{k}$ triangles, $< 5\text{ MB}$) for seamless projective travel transitions, dollhouse orbit view, and collision backdrops.
3. **Navigation Layer**: Floor-aligned 2D occupancy grid (`nav/navgrid.json` @ 5 cm) + 3D navmesh (`mesh/navmesh.glb` for `three-pathfinding`) with A* / Theta* pathfinding.
4. **Photoreal Mode (Optional)**: 3D Gaussian Splatting (`.splat`) rendered as an optional secondary tab without degrading core navigation or browser performance.

---

## Unified Pipeline CLI

Run the entire pipeline or individual stages via the unified entry point:

```bash
# Full pipeline execution
python -m pipeline.run --input <video_or_frames_folder> --out out/ --config config.yaml

# Run with specific pose backend and metric scale reference (e.g., 2.0m door height)
python -m pipeline.run --input test/sample_data/frames --out out/ --pose-backend auto --metric-reference 2.0 --skip-splat

# Re-run specific stages
python -m pipeline.run --input test/sample_data/frames --out out/ --stages pose,align,panos
```

### Supported Pose Backends (`--pose-backend`)
- `colmap`: Incremental SfM using COLMAP (SIFT + sequential matching + global bundle adjustment). High precision and robust convergence.
- `vggt`: Feed-forward windowed pose estimation chunked into overlapping windows of $N$ frames to fit within VRAM, aligned via closed-form Sim(3) / Umeyama transformation on the overlaps.
- `auto` (Default): Runs VGGT feed-forward first; verifies registration health ($\ge 70\%$ registered, $\le 4.0\text{ px}$ residual error), falling back cleanly to COLMAP if reconstruction is broken.

---

## Milestone M1: Pose Backend Benchmark

Benchmark executed on the 30-frame sample indoor dataset (`test/sample_data/frames`) with an optional metric reference of $2.0\text{ m}$:

```bash
python -m bench.poses --frames test/sample_data/frames --out test/bench_poses
```

### Benchmark Comparison

| Backend | Runtime (s) | Registered Frames | Reprojection Error | Sparse 3D Points | Scaling Method | Characteristics |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **COLMAP** | **32.32 s** | **30 / 30 (100.0%)** | **1.161 px** | 5,314 | `reference` (2.0 m) | Rigorous iterative bundle adjustment; standard BSD-3 license. |
| **VGGT** | **68.87 s** | **30 / 30 (100.0%)** | **0.354 px** | 10,313 | `reference` (2.0 m) | Feed-forward windowed Sim(3) Umeyama; bounded VRAM footprint (<4GB). |

*Hardware: 13th Gen Intel Core i9-13900HX, NVIDIA GeForce RTX 4060 Laptop GPU (8GB VRAM).*

---

## Quick Start & Web App

### 1. Backend & Static Server
```bash
cd backend
pip install -r requirements.txt
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```
- API Docs: `http://localhost:8000/docs`
- Static Assets & Tour API: `http://localhost:8000/api/tour/sample_scene`

### 2. Frontend Web Viewer
```bash
cd frontend
npm install
npm run dev
```
- Web Application: `http://localhost:5173`

---

## Licensing & Compliance (Rule 4)

All third-party libraries, packages, and pre-trained models are credited with their license terms in [`THIRD_PARTY_LICENSES.md`](THIRD_PARTY_LICENSES.md). Non-commercial checkpoints (such as Inria 3DGS and Meta VGGT-1B) are flagged and isolated behind modular interfaces; the production pipeline is completely runnable on permissive open-source licenses (MIT, BSD-3, Apache 2.0).
