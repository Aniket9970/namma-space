# Namma Space — Indoor Spatial Engine

> **Techfest IIT Bombay Hackathon Project**

Namma Space is an end-to-end pipeline that turns a smartphone video of any indoor space into an interactive 3D web viewer with free-roam navigation, POI labels, and A\*-powered pathfinding.

---

## System Overview

```
Smartphone Video
      │
      ▼
[Windows RTX 4060] ── reconstruction/
  • COLMAP (SfM)
  • Nerfstudio (NeRF → mesh)
  • 3D Gaussian Splatting
  • export_web.py → scene.glb + scene.splat
  • build_occupancy_grid.py → grid.npy + meta
      │
      ▼  (copy files to backend/static/)
[Mac M4] ── backend/  +  frontend/
  • FastAPI serves models & REST API
  • React + Three.js viewer
  • WASD free-roam, POI markers, glowing path
```

---

## Quick Start

```bash
# 1 — Install dependencies
make install-backend
make install-frontend

# 2 — Run both servers
make dev
```

Frontend: http://localhost:5173  
Backend API docs: http://localhost:8000/docs

---

## Directory Structure

```
namma_space/
├── reconstruction/   # GPU scripts (run on teammate's Windows machine)
├── backend/          # FastAPI server (Mac M4)
├── frontend/         # React + Three.js viewer (Mac M4)
├── docs/             # SOP + technical abstract outline
├── test/             # Sample data info
├── Makefile
├── docker-compose.yml
└── README.md
```

---

## Workflow

1. **Capture** — Follow `docs/SOP.md` for indoor capture guidelines.
2. **Reconstruct** — On the Windows GPU machine run scripts in `reconstruction/` (see its `README.md`).
3. **Copy outputs** — Place `scene.glb`, `scene.splat`, `grid.npy`, `occupancy_meta.json` into `backend/static/`.
4. **Serve** — `make dev` starts both servers.
5. **Explore** — Open the browser, load a scene, explore, add POIs, find paths.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Reconstruction | COLMAP, Nerfstudio, 3D Gaussian Splatting, Open3D, Trimesh |
| Backend | FastAPI, SQLAlchemy (async), SQLite, SciPy |
| Frontend | React 18, Vite, Three.js, @react-three/fiber, @react-three/drei |
| Pathfinding | A\* on 2D occupancy grid |
