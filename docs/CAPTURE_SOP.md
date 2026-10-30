# Namma Space — Venue Capture Standard Operating Procedure (SOP)
> **Techfest IIT Bombay 2026-27 | Smartphone Capture Protocol**

This protocol defines the exact procedure for capturing any indoor space (hall, meeting room, exhibition stall, or residential apartment) using a standard smartphone to guarantee 100% reconstruction success, seam-free 360 panorama nodes, and millimeter-accurate obstacle-aware navmeshes.

---

## 1. Phone Camera Hardware & Settings

Before stepping into the venue, configure the smartphone camera:

| Parameter | Recommended Setting | Reason |
| :--- | :--- | :--- |
| **Resolution** | 4K UHD ($3840 \times 2160$) or 1080p ($1920 \times 1080$) | Preserves fine wall, door, and baseboard features. |
| **Frame Rate** | 30 FPS or 60 FPS | Guarantees smooth optical flow between keyframes. |
| **Lens** | Primary Wide (1x) | Avoid ultrawide lens barrel distortion unless calibrated. |
| **Stabilization** | ON (Optical / EIS) | Prevents rolling shutter and high-frequency motion blur. |
| **Exposure / White Balance** | **LOCKED (AE/AF Lock)** | Prevents brightness flickering during 360 spins. |
| **Orientation** | Landscape | Maximizes horizontal field-of-view for spherical warping. |

---

## 2. Venue Preparation (Pre-Flight Checklist)

1. **Static Environment**: Ensure no people, pets, or moving objects are in the capture volume.
2. **Doors & Partitions**: Wedge all interior doors fully open or fully closed (avoid doors swinging mid-capture).
3. **Lighting**: Turn on all interior ceiling and ambient lights. Open blinds evenly to avoid high-contrast sunlight hotspots.
4. **Reference Scale Marker (Optional for Metric Calibration)**:
   - Note the height of a standard doorway ($2.00\text{ m}$ or $2.10\text{ m}$), or place a 1.0 m measuring tape on the floor.
   - Pass this value to the pipeline entry point: `--metric-reference 2.0`.

---

## 3. Walking & Scanning Trajectory (The "Stop-and-Spin" Protocol)

The capture trajectory consists of a continuous video that alternates between **vantage node spins** and **slow walking translation**:

```
[Entrance: Node 0] ──(slow walk 2.5m)──▶ [Node 1: 360° Spin] ──(slow walk 2.5m)──▶ [Node 2: 360° Spin]
```

### Phase A: Node Spin (At each 2.5m vantage point)
1. Stand at the planned node position (e.g. center of a room, doorway threshold, hallway junction).
2. Hold the phone upright at chest/eye level ($\approx 1.55\text{ m} - 1.65\text{ m}$).
3. Rotate your body in a complete **360-degree circle slowly over 10 to 15 seconds** (roughly 25–30 degrees per second).
4. Keep the camera centered over the pivot axis (rotate phone around its own lens, not around an outstretched arm).

### Phase B: Translation (Between consecutive nodes)
1. Once the 360-degree rotation completes, slowly walk forward along the natural pedestrian path toward the next node.
2. Maintain a slow, deliberate pace ($\approx 0.5\text{ m/s}$).
3. Keep the camera pointed forward with a slight $10^\circ$ downward pitch to capture both the floor and front obstacles.
4. Space adjacent nodes approximately **2.0 to 3.0 metres apart**. Never exceed 3.5 metres to ensure line-of-sight connectivity.

### Phase C: Loop Closure
- If capturing a multi-room venue or loop hallway, end the recording by walking back into the starting node and recording a quick 3-second overlapping view of the entrance. This provides loop-closure constraints for the bundle adjuster.

---

## 4. Common Capture Pitfalls & Avoidance

| Pitfall | Consequence | How to Avoid |
| :--- | :--- | :--- |
| **Fast Panning** | Motion blur causes Laplacian sharpness failure. | Rotate phone at a steady 12-second pace per 360 spin. |
| **Walking People** | Creates ghost artifacts in proxy mesh and navgrid. | Ask venue occupants to stand outside during the 3-minute scan. |
| **Pure White Featureless Walls** | Sparse SfM feature starvation. | Keep floor/baseboards and doorframes in frame. |
| **Auto-Exposure Pumping** | Seam discoloration between panorama frames. | Long-press screen to engage **AE/AF Lock** before starting. |

---

## 5. Turnaround & Scalability Benchmark

For our target **50 m² venue** running on an **NVIDIA RTX 4060 Laptop GPU**:

| Stage | Duration | Scaling Behavior |
| :--- | :--- | :--- |
| **Keyframe Extraction** | ~10s | Linear with video length ($O(T)$). |
| **Pose Estimation (SfM)** | ~45s - 90s | $O(N)$ with sequential matching; VGGT windowing fits in 4GB VRAM. |
| **Floor Alignment** | ~1s | Fast RANSAC on point cloud ($O(K)$). |
| **Equirectangular Panoramas** | ~60s - 90s | Linear with node count (~15s per 4096x2048 node). |
| **Depth & Proxy Mesh** | ~10s | GPU inference + Open3D Poisson surface reconstruction. |
| **NavGrid & NavMesh** | ~2s | Vectorized NumPy height slicing and quad meshing. |
| **Packaging & Web Export** | ~1s | SQLite sync and JSON manifest generation. |
| **Total Pipeline Turnaround** | **< 4.5 minutes** | **Well within the 15-minute competition ceiling.** |

