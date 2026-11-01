# Third-Party Licenses Ledger
### Namma Space | Techfest IIT Bombay 2026-27

In compliance with Competition Rule 4, all third-party libraries, frameworks, pre-trained models, and datasets are credited below with their exact license types and commercial/academic usage restrictions.

---

## 1. Core Frameworks & Runtimes

| Component | Version | License | Source / Repository | Commercial / Competition Use |
|---|---|---|---|---|
| **Python** | 3.10+ | PSF License | python.org | Permitted |
| **Node.js** | 20+ | MIT | nodejs.org | Permitted |
| **FastAPI** | >=0.110.0 | MIT | github.com/tiangolo/fastapi | Permitted |
| **React** | 18.3.0 | MIT | github.com/facebook/react | Permitted |
| **Three.js** | 0.167.0 | MIT | github.com/mrdoob/three.js | Permitted |
| **@react-three/fiber** | 8.17.0 | MIT | github.com/pmndrs/react-three-fiber | Permitted |
| **@react-three/drei** | 9.109.0 | MIT | github.com/pmndrs/drei | Permitted |
| **Zustand** | 4.5.0 | MIT | github.com/pmndrs/zustand | Permitted |
| **Vite** | 5.4.0 | MIT | github.com/vitejs/vite | Permitted |

---

## 2. Geometry, Computer Vision & Reconstruction

| Component | License | Permitted Usage | Notes / Restrictions |
|---|---|---|---|
| **COLMAP** (4.2+) | BSD-3-Clause | Permitted | Core Structure-from-Motion engine. Free for academic & commercial use. |
| **OpenCV** (`opencv-python`) | Apache 2.0 | Permitted | Equirectangular warping, feature matching, image blending. |
| **Trimesh** | MIT | Permitted | Raycasting, collision geometry, mesh export. |
| **Open3D** | MIT | Permitted | TSDF depth fusion, point cloud processing, mesh decimation. |
| **SciPy / NumPy** | BSD-3-Clause | Permitted | Linear algebra, plane fitting, morphology, spatial grids. |
| **PyTorch** | BSD-3-Clause | Permitted | Tensor compute backend. |

---

## 3. 3DGS & Advanced Model Ledger (Status & Licensing Flag)

| Model / Library | Stated License | Commercial Use | Competition Assessment & Fallback Strategy |
|---|---|---|---|
| **Inria 3D Gaussian Splatting** | Non-Commercial Research License | **RESTRICTED** | Used ONLY for the optional "Photoreal" viewer tab. **Never required for core navigation, proxy mesh, or photosphere tour.** |
| **VGGT** (Visual Geometry Grounded Transformer, Meta / Oxford) | Meta Research License (v1, July 2025) / Non-Commercial Checkpoint | **FLAGGED (NON-COMMERCIAL CHECKPOINT)** | Core code under Meta Research License. Default checkpoint `facebook/VGGT-1B` is non-commercial/academic only; `facebook/VGGT-1B-Commercial` requires application. **Strictly isolated behind `PoseBackend` interface; pipeline defaults/falls back to BSD-3 COLMAP.** |
| **Depth Anything V2** | Apache 2.0 | Permitted | Metric/relative monocular depth. Base model weights under Apache 2.0. |
| **DA360 / Depth Any Panoramas** | Apache 2.0 / MIT | Permitted | Panorama-native depth estimation wrapped behind `PanoDepth` interface. |
| **three-pathfinding** | MIT | Permitted | Browser navmesh traversal and `clampStep` constrained free-roaming. |
| **Fuse.js** | Apache 2.0 | Permitted | Client-side fuzzy search over POI names, aliases, and categories. |

---

## 4. Verification Policy
- Any component under a non-commercial (NC) license must be marked as an optional experimental plugin or replaced with an Apache 2.0 / BSD / MIT alternative for competition production deliverables.
- Core deliverables (Pano nodes, proxy mesh, navmesh, A* planner, zero-install web viewer) rely strictly on permissive open-source licenses (MIT, BSD-3, Apache 2.0).

