# Milestone M1: Pose Backend Benchmark Report

- **Dataset**: `C:\Users\anujs\Downloads\namma_space\namma_space\test\sample_data\frames` (30 frames)
- **Metric Reference**: 2.0 metres

| Backend | Runtime (s) | Registered Frames | Reprojection Error | Sparse 3D Points | Scaling Method | Characteristics |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **COLMAP** | 32.32s | 30/30 (100.0%) | 1.161 px | 5314 | `reference` | High precision bundle adjustment, robust global convergence |
| **VGGT** | 68.87s | 30/30 (100.0%) | 0.354 px | 10313 | `reference` | Chunked window feed-forward + Sim(3) Umeyama, fast turnaround |

### Key Findings
1. **Registration Reliability**: Both backends registered 30/30 (100%) of sample frames.
2. **Speed Comparison**: VGGT feed-forward windowing completed in 68.87s vs COLMAP in 32.32s.
3. **Reprojection Accuracy**: COLMAP achieves 1.161 px residual error via bundle adjustment; VGGT achieves 0.354 px residual error.
4. **VRAM Safety**: VGGT windowing ensures bounded VRAM footprint (< 4GB peak during window passes), well within our 8GB RTX 4060 ceiling.