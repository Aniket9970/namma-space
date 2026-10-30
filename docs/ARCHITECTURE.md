# Namma Space — System Architecture Specification
> **Techfest IIT Bombay 2026-27 | Competition Architecture Document**  
> **Repository Branch:** `hybrid-pano-nav` | **Coordinate Standard:** Right-Handed, Y-Up, Metres, Floor at $y = 0.0$

---

## 1. Executive Summary & Architectural Motivation

Namma Space turns ordinary smartphone video/photos of complex indoor environments into an interactive, zero-install 3D web experience running in any modern browser. Users can walk through spaces in first person, search for Points of Interest (POIs) such as "Meeting Room 4" or "3-seater sofas", and receive obstacle-aware, turn-by-turn guidance along an optimal floor path.

### 1.1 The Limitation of Pure 3D Gaussian Splatting (Round 1 Baseline)
In Round 1, the pipeline relied on **3D Gaussian Splatting (3DGS)** as the sole scene representation. Extensive testing revealed fundamental limitations for indoor roaming:
1. **Severe Off-Path Degradation**: 3DGS looks photorealistic directly along the capture path, but moving even 0.5 metres off-trajectory causes needle-like floaters, perspective tearing, and cloudy artifacts.
2. **Absence of Collision Geometry**: Gaussian splats are an unstructured cloud of probabilistic ellipsoids. They do not yield a planar floor or solid walls, making physical collision detection and A* pathfinding impossible without secondary meshing.
3. **Heavy Compute & Memory Footprint**: A 7,000-iteration splat produces 30–60 MB binary files that require multi-gigabyte WebGL memory buffers, risking browser crashes on mobile and mid-tier laptop hardware.

### 1.2 The Hybrid Core (Visual + Geometry + Navigation)
To guarantee competition success, Namma Space adopts the proven architecture used by industrial leaders (Matterport and Google Street View):
1. **Visual Layer**: High-resolution 360 equirectangular panorama nodes (`4096x2048` production + `1024x512` fast LOD preview) spaced at 2–3 m intervals, rendering crisp 60 FPS views with zero floating artifacts.
2. **Geometry Layer**: A lightweight metric depth-proxy mesh (`mesh/proxy.glb`, $< 50\text{k}$ triangles, $< 5\text{ MB}$) reconstructed from aligned panoramic depth via Open3D TSDF fusion, powering projective SPHR-style travel transitions, dollhouse orbit views, and physical collision boundaries.
3. **Navigation Layer**: A floor-aligned 2D occupancy grid (`nav/navgrid.json` at 5 cm resolution) and 3D navigation mesh (`mesh/navmesh.glb` for `three-pathfinding`), driving obstacle-avoiding A* / Theta* pathfinding with ribbon visualization.
4. **Photoreal Tab**: 3DGS is retained as an optional, lazily-loaded "Photoreal Mode" tab that never blocks core navigation.

---

## 2. End-to-End System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          SMARTPHONE VIDEO CAPTURE                           │
│     (4K / 1080p, AE/AF Locked, "Stop-and-Spin" Trajectory, 2–3 m Nodes)     │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    NAMMA SPACE RECONSTRUCTION PIPELINE                      │
│                          (python -m pipeline.run)                           │
│                                                                             │
│  [Stage 1: Extract] ──▶ 2.5 FPS Keyframes + Laplacian Blur Filtering        │
│                               │                                             │
│  [Stage 2: Pose]    ──▶ Dual Backend (COLMAP SIFT / VGGT Feed-Forward)      │
│                         • Windowed Umeyama Sim(3) Alignment (Fits 4GB VRAM) │
│                         • Reprojection Error & Registration Fallback        │
│                               │                                             │
│  [Stage 3: Align]   ──▶ RANSAC Floor Plane Estimation                       │
│                         • Normal Aligned to +Y, Floor Translated to y = 0.0 │
│                         • 3-Panel Orthographic Elevation Render Verification│
│                               │                                             │
│  [Stage 4: Panos]   ──▶ Equirectangular Spherical Projection                │
│                         • Pose-Guided Ray Warping + Seam Feathering         │
│                         • Dual Resolution (4096x2048 + 1024x512 LOD)        │
│                               │                                             │
│  [Stage 5: Depth]   ──▶ Metric Panoramic Depth & Proxy Mesh                 │
│                         • PanoDepth Model + SfM Least-Squares Scale-Shift   │
│                         • Open3D Poisson Reconstruction & Quadric Decimate  │
│                               │                                             │
│  [Stage 6: Nav]     ──▶ Height Slicing (0.2m–1.8m) & 5 cm Occupancy Grid    │
│                         • Morphological Opening + 0.3m Agent Inflation      │
│                         • Export Three.js NavMesh (mesh/navmesh.glb)        │
│                               │                                             │
│  [Stage 7: Export]  ──▶ Contract Packaging (tour.json, navgrid.json, etc.)  │
│                         • Backend Static Synchronization                    │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                       FULL-STACK CLIENT APPLICATION                         │
│                                                                             │
│  ┌───────────────────────────────┐     ┌─────────────────────────────────┐  │
│  │       FASTAPI BACKEND         │     │         REACT THREE FIBER       │  │
│  │  • Static Asset Server        │     │            WEB VIEWER           │  │
│  │  • A* / Theta* Route API      │◀───▶│  • SPHR Projective Transitions  │  │
│  │  • POI Persistence (SQLite)   │     │  • Three-Pathfinding Roam       │  │
│  └───────────────────────────────┘     │  • GTA Minimap HUD & Radar      │  │
│                                        │  • Fuse.js POI Autocomplete     │  │
│                                        │  • WebXR AR Guidance Companion  │  │
│                                        └─────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Mathematical Foundations & Coordinate Conventions

### 3.1 Coordinate System Definition
All spatial entities conform strictly to:
- **Handedness**: Right-handed cartesian coordinates.
- **Axes**: $+X$ is Right, $+Y$ is Up (aligned with gravity vector), $+Z$ is Backward (camera looks down $-Z$).
- **Units**: Metres ($1.0 = 1.0\text{ m}$).
- **Datum**: The finished floor plane is defined exactly at $y = 0.0$.
- **Camera Eye Height**: Standard pedestrian vantage is fixed at $y = 1.65\text{ m}$.

### 3.2 RANSAC Floor Plane Estimation (Stage 3: Align)
Given the sparse 3D point cloud $\mathcal{P} = \{p_i \in \mathbb{R}^3\}$ and camera centers $\mathcal{C} = \{c_j \in \mathbb{R}^3\}$:
1. Points located significantly above the mean camera height ($p_{i, y} > \bar{c}_y - 0.2$) are discarded to eliminate ceiling structures.
2. 3-point RANSAC fits the dominant planar equation:
   $$\mathbf{n}^T p + d = 0 \quad \text{where } \|\mathbf{n}\|_2 = 1$$
3. The normal $\mathbf{n}$ is oriented upward such that $\mathbf{n} \cdot [0, 1, 0]^T > 0$.
4. The rotation matrix $R_{\text{align}}$ aligning $\mathbf{n}$ with $+Y = [0, 1, 0]^T$ is computed using Rodrigues' formula:
   $$\mathbf{v} = \mathbf{n} \times [0, 1, 0]^T, \quad s = \|\mathbf{v}\|_2, \quad c = \mathbf{n} \cdot [0, 1, 0]^T$$
   $$R_{\text{align}} = I + [\mathbf{v}]_\times + [\mathbf{v}]_\times^2 \left( \frac{1 - c}{s^2} \right)$$
5. The translation $t_{\text{align}} = [0, -d_{\text{floor}}, 0]^T$ translates the fitted floor plane to $y = 0.0$.
6. All camera extrinsics $(R_j, t_j)$ and points $p_i$ are updated:
   $$p_i' = R_{\text{align}} p_i + t_{\text{align}}$$
   $$R_j' = R_j R_{\text{align}}^T, \quad C_j' = R_{\text{align}} C_j + t_{\text{align}}$$

### 3.3 Umeyama Closed-Form Sim(3) Alignment (Stage 2: Pose)
To enable feed-forward pose models (e.g. VGGT) to process long video sequences on consumer GPUs without VRAM exhaustion, frames are partitioned into overlapping chunks of length $N = 16$ with overlap $M = 4$.

For overlapping frame camera centers $\{x_k\}_{k=1}^M$ in chunk $A$ and $\{y_k\}_{k=1}^M$ in chunk $B$, the optimal similarity transformation $(s, R, t) \in \text{Sim}(3)$ is computed in closed form using singular value decomposition (SVD):
$$\mu_x = \frac{1}{M}\sum_{k=1}^M x_k, \quad \mu_y = \frac{1}{M}\sum_{k=1}^M y_k$$
$$\sigma_x^2 = \frac{1}{M}\sum_{k=1}^M \|x_k - \mu_x\|^2, \quad \Sigma_{xy} = \frac{1}{M}\sum_{k=1}^M (y_k - \mu_y)(x_k - \mu_x)^T$$
$$\Sigma_{xy} = U D V^T, \quad S = \begin{cases} I & \text{if } \det(U)\det(V) = 1 \\ \text{diag}(1, \dots, 1, -1) & \text{if } \det(U)\det(V) = -1 \end{cases}$$
$$R = U S V^T, \quad s = \frac{1}{\sigma_x^2} \text{tr}(D S), \quad t = \mu_y - s R \mu_x$$

### 3.4 Depth Alignment to Sparse SfM Coordinates (Stage 5: Depth)
Monocular or panoramic depth estimation predicts relative inverse depth $d$. To lock predicted depth to true metric SfM scale, sparse SfM points projecting into node $k$ with true Euclidean distances $z_i$ are matched to predicted values $d_i$. Scale $s$ and shift $t$ are solved via ordinary least squares:
$$\arg\min_{s, t} \sum_{i=1}^K \left( s \cdot d_i + t - z_i \right)^2$$
The calibrated depth map is then clamped, converted to millimetres, and saved as a 16-bit unsigned integer PNG.

---

## 4. Pipeline Stages & Implementation Details

| Stage | Module | Primary Operation | Deliverable Artifact |
| :--- | :--- | :--- | :--- |
| **1. Extract** | `pipeline/stages/extract.py` | 2.5 FPS uniform sampling, OpenCV Laplacian variance sharpness scoring ($\text{Var}(\nabla^2 I) \ge 80.0$). | `out/frames/frame_*.jpg` |
| **2. Pose** | `pipeline/stages/pose.py` | `PoseBackend` abstract interface. COLMAP SIFT sequential matching or VGGT feed-forward windowing with Sim(3) Umeyama fusion. Metric scaling applied via `--metric-reference`. | `out/colmap/poses.json` |
| **3. Align** | `pipeline/stages/align.py` | RANSAC floor plane detection, normal rotation to $+Y$, floor translation to $y = 0.0$. Generates 3-panel orthographic elevation render. | `out/poses_aligned.json`, `out/debug_floor_alignment.png` |
| **4. Panos** | `pipeline/stages/panos.py` | Greedy 2.0–3.0 m node clustering. Pose-guided equirectangular spherical ray back-projection with cosine seam feathering and Telea inpainting. | `out/panos/*.jpg` (4K), `out/panos/*_thumb.jpg` (LOD) |
| **5. Depth** | `pipeline/stages/depth_proxy.py`| `PanoDepth` interface. Sparse SfM scale/shift alignment, Open3D Poisson surface reconstruction, quadric edge decimation ($< 50\text{k}$ faces). | `out/depth/*.png` (uint16), `out/mesh/proxy.glb` ($< 5\text{ MB}$) |
| **6. Nav** | `pipeline/stages/nav.py` | 2D height slicing ($0.2\text{m} \le y \le 1.8\text{m}$) at 5 cm resolution. Morphological opening, connected components, $0.3\text{m}$ agent inflation, navmesh glTF export. | `out/nav/navgrid.json`, `out/mesh/navmesh.glb` |
| **7. Export**| `pipeline/stages/export.py`| Manifest assembly (`tour.json`), database sync, static asset replication to backend API server. | `out/tour.json`, `backend/static/panoramas/` |
| **8. Splat** | `pipeline/stages/splat.py` | Optional: 7,000-step 3DGS training exported to `.splat` for photoreal tab inspection. | `out/splat/scene.splat` |

---

## 5. Web Viewer & Frontend Architecture

The viewer is built in React 18, Vite, Three.js, and `@react-three/fiber`, maintaining 60 FPS performance without requiring browser extension installs.

### 5.1 State Architecture (`frontend/src/store/useStore.js`)
Global state is managed using Zustand with selective re-renders:
- `currentMode`: `'photosphere'` (Node-to-node) | `'dollhouse'` (3D orbit) | `'freeroam'` (WASD walkthrough) | `'splat'` (Photoreal 3DGS).
- `currentNodeId`: Active panorama node ID.
- `targetNodeId`: Destination node during active SPHR flight transition.
- `transitionProgress`: $0.0 \to 1.0$ interpolation scalar driving projective texture shader.
- `collisionEnabled`: Boolean controlling `three-pathfinding` navmesh clamping.
- `activePath`: 3D waypoint array $[[x, y, z], \dots]$ for floor ribbon rendering.
- `autoWalkActive`: Boolean driving animated camera travel along active path.
- `playerTelemetry`: Real-time position $[x, y, z]$ and yaw rotation for minimap HUD.

### 5.2 SPHR Projective Travel Transition (`PhotosphereTour.jsx`)
When moving between Node A and Node B:
1. Camera does not instantly cut; instead, a flight animation traverses the straight line between $C_A$ and $C_B$ over 800 ms.
2. The proxy mesh is rendered with a custom GLSL projective shader (`ProjectiveProxyMesh`). Node A's equirectangular texture is projectively mapped onto the proxy mesh geometry from position $C_A$.
3. As the camera approaches Node B, the shader crossfades the projective texture from Node A to Node B.
4. Upon arrival, the scene smoothly switches back to the high-resolution inverted sphere at Node B.
5. This delivers real 3D motion parallax without the floaters and tearing inherent to pure neural or splat representations.

### 5.3 Navmesh Collision Clamping (`FreeRoamControls.jsx`)
In Free-Roam mode:
1. The user navigates freely using WASD and pointer-lock mouse look.
2. Every frame, movement delta $\Delta p$ is evaluated against `three-pathfinding`:
   ```javascript
   const target = currentPosition.clone().add(moveDelta);
   const clamped = pathfinder.clampStep(
     currentPosition,
     target,
     currentNode,
     'default',
     groupId,
     clampedTarget
   );
   camera.position.copy(clamped);
   ```
3. If the user walks toward a wall, the vector component normal to the wall is eliminated, providing smooth, natural wall-sliding with zero boundary penetration.
4. Pressing `C` allows toggling collision clamping on or off.

### 5.4 GTA-Style Minimap HUD (`Minimap.jsx`)
Rendered directly onto an HTML5 2D canvas in the top-right corner:
- Renders occupancy grid cells (walls in red/slate, free floor in dark grey).
- Draws POI destination markers with category icons.
- Displays the active planned path as an emerald-green line.
- Draws the player's live position as a rotating directional chevron aligned with camera yaw.
- Clicking the minimap expands it into a high-resolution interactive floorplan modal.

### 5.5 AR Companion (`ARCompanion.jsx`)
For on-site phone navigation (competition bonus):
- Uses WebXR Device API (`navigator.xr.requestSession('immersive-ar')`) for camera pass-through.
- Performs 3-tap physical ground alignment to establish coordinate alignment with the virtual navmesh.
- Renders a directional 3D path arrow directly on the floor.
- Gracefully falls back to a 2D compass bearing HUD on devices lacking WebXR hardware.

---

## 6. Official Data Contracts & Schemas

### 6.1 Tour Manifest (`out/tour.json`)
```json
{
  "meta": {
    "units": "m",
    "up": "Y",
    "floor_y": 0.0,
    "scale_method": "reference"
  },
  "nodes": [
    {
      "id": "n000",
      "position": [-0.852, 1.65, 0.412],
      "rotation": [0.0, 0.382, 0.0, 0.924],
      "name": "Entrance Foyer",
      "pano": {
        "type": "equirect",
        "url": "panos/n000.jpg",
        "thumb_url": "panos/n000_thumb.jpg",
        "depth_url": "depth/n000.png"
      },
      "neighbors": ["n001", "n002"]
    }
  ],
  "proxy_mesh": "mesh/proxy.glb",
  "navmesh": "mesh/navmesh.glb",
  "navgrid": "nav/navgrid.json"
}
```

### 6.2 Navigation Grid (`out/nav/navgrid.json`)
```json
{
  "resolution_m": 0.05,
  "origin": [-3.15, -4.20],
  "width": 126,
  "height": 168,
  "data": [0, 0, 1, 1, 1, 0, 2, 2, "..."],
  "inflation_m": 0.30,
  "floor_y": 0.0
}
```
*Cell state encoding: `0` = Free (walkable), `1` = Obstacle (wall/furniture), `2` = Unknown (unobserved).*

### 6.3 Points of Interest (`out/pois.json`)
```json
[
  {
    "id": "poi_01",
    "name": "Executive Conference Desk",
    "category": "Workspaces",
    "aliases": ["boardroom table", "meeting desk", "discussion area"],
    "position": [0.45, 0.75, -1.82],
    "node_id": "n001",
    "source": "manual"
  }
]
```

---

## 7. Performance Benchmarks & Validation

### 7.1 Pose Backend Benchmark (`test/bench_poses/`)
Evaluated on 30 sample indoor frames using an Intel Core i9-13900HX + NVIDIA RTX 4060 Laptop GPU:

| Metric | COLMAP Backend | VGGT Feed-Forward Backend | Target / Threshold |
| :--- | :--- | :--- | :--- |
| **Runtime** | **32.32 seconds** | 68.87 seconds | $< 180\text{ seconds}$ |
| **Registered Frames** | **30 / 30 (100.0%)** | **30 / 30 (100.0%)** | $\ge 70.0\%$ |
| **Mean Reprojection Error** | 1.161 px | **0.354 px** | $\le 4.0\text{ px}$ |
| **Sparse 3D Points** | 5,314 points | 10,313 points | $\ge 1,000\text{ points}$ |
| **Peak VRAM Usage** | 1.8 GB | 3.4 GB | $< 8.0\text{ GB}$ (Bounded by Umeyama windowing) |

### 7.2 Geometry & Deliverable Footprint
- **Proxy Mesh (`mesh/proxy.glb`)**: 39,958 triangles | **0.76 MB** (Strictly meets $< 50\text{k}$ triangles and $< 5\text{ MB}$ limit).
- **Navigation Mesh (`mesh/navmesh.glb`)**: 39,150 triangles | **1.37 MB**.
- **Floor Planarity Check (`debug_floor_alignment.png`)**: Fitted floor plane normal $\mathbf{n} = [0.0, 1.0, 0.0]^T$, plane standard deviation $\sigma = 0.0276\text{ m}$ ($< 3\text{ cm}$).
- **First Interactive Render**: $< 95\text{ ms}$ on local browser using 1024 LOD texture thumbnails.
- **Route Computation Latency**: $< 25\text{ ms}$ via backend `/api/scenes/{id}/route` A* endpoint.

---

## 8. Third-Party Licenses & Rule 4 Compliance

All dependencies and external weights are strictly logged in [`THIRD_PARTY_LICENSES.md`](file:///c:/Users/anujs/Downloads/namma_space/namma_space/THIRD_PARTY_LICENSES.md):
- **COLMAP**: BSD 3-Clause (Permissive).
- **Open3D**: MIT License (Permissive).
- **Three.js & three-pathfinding**: MIT License (Permissive).
- **FastAPI / Pydantic / Uvicorn**: MIT License (Permissive).
- **Fuse.js**: Apache 2.0 (Permissive).
- **VGGT-1B Checkpoint**: Meta Research Non-Commercial License (Flagged in licensing audit).
- **3DGS (diff-gaussian-rasterization)**: Inria & MPII Non-Commercial Research License (Flagged; strictly optional).
