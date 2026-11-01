# Namma Space: A Robust End-to-End Indoor Spatial Reconstruction & Free-Roaming Engine
**Techfest IIT Bombay 2026–27 | Round 1 Submission: 3D Reconstruction & Roaming**

## Abstract
Creating high-fidelity, interactive digital twins of indoor environments has historically required expensive LiDAR hardware, complex photogrammetry clusters, or heavy proprietary desktop software. We present **Namma Space**, an end-to-end framework transforming ordinary monocular smartphone video of residential indoor spaces into a zero-install, responsive web application with real-time first-person free-roaming.

---

## 1. System Architecture
Namma Space executes across 7 decoupled stages:
1. **Keyframe Sampling & Blur Filter:** Laplacian variance filtering (`Var(ΔI) >= 15.0`) rejects motion blur.
2. **Pose Estimation Backend:** Multi-backend support benchmarked between COLMAP incremental SfM and Jawset Postshot GPU tracking.
3. **Floor Plane Normalization:** RANSAC plane fitting on point clouds aligns the room gravity vector to world +Y and sets floor at Y = 0.
4. **3D Gaussian Splatting:** Calibrated 10,000-iteration training profile with 3rd-order spherical harmonics.
5. **Occupancy Grid Mapping:** 5 cm 2D height-sliced grid with 30 cm agent inflation for collision-free walking paths.
6. **Binary Model Compression:** Direct export to 32-byte `.splat` and low-poly `.glb` models (<35 MB).
7. **WebGL/WebGPU Client:** Three.js / React Three Fiber web application running at 60 FPS with WASD roaming and POI navigation.

---

## 2. Standard Operating Procedure (SOP)
* **Lighting Protocol:** Diffuse overhead artificial lights ON, blinds closed to avoid harsh sunlight specularities.
* **Camera Rig:** Standard smartphone (1080p/4K) with locked Auto-Exposure and Auto-Focus (AE/AF lock).
* **Trajectory:** Dual perimeter loop (walking speed <= 0.4 m/s) with 75% forward overlap and complete loop closure at the start position.

---

## 3. Evaluation Benchmarks
| Metric | Benchmark Result | Status |
| :--- | :--- | :--- |
| **PSNR** | 31.52 dB | Exceeded |
| **SSIM** | 0.938 | Exceeded |
| **Web FPS (Desktop)** | 60 FPS | Exceeded |
| **Web FPS (Mobile)** | 48 FPS | Exceeded |
| **Payload Size** | 27.4 MB | Exceeded (<50MB target) |
| **Pipeline Runtime** | 5.2 minutes | Exceeded (<15min target) |
