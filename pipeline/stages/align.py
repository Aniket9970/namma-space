"""
pipeline/stages/align.py
────────────────────────
Stage 3: RANSAC Floor Plane Fitting & Coordinate Alignment.
Identifies the dominant floor plane, rotates it to Y-up (+Y), and translates floor to y = 0.
Transforms all camera poses and landmark points into the canonical metric frame.
"""

import json
from pathlib import Path
from typing import Any, Dict, Tuple
import numpy as np
import trimesh

from .base import BaseStage
from ..config import PipelineConfig


def fit_plane_ransac(points: np.ndarray, dist_threshold: float = 0.05, max_iters: int = 2000) -> Tuple[np.ndarray, float, np.ndarray]:
    """Fit a plane equation (ax + by + cz + d = 0, with ||n|| = 1) using RANSAC."""
    best_inliers = np.array([], dtype=int)
    best_plane = np.array([0.0, 1.0, 0.0, 0.0])
    N = len(points)
    if N < 3:
        return best_plane[:3], float(best_plane[3]), np.arange(N)

    for _ in range(max_iters):
        sample_idx = np.random.choice(N, 3, replace=False)
        p1, p2, p3 = points[sample_idx]
        v1 = p2 - p1
        v2 = p3 - p1
        normal = np.cross(v1, v2)
        norm = np.linalg.norm(normal)
        if norm < 1e-6:
            continue
        normal = normal / norm
        d = -np.dot(normal, p1)

        dists = np.abs(np.dot(points, normal) + d)
        inliers = np.where(dists < dist_threshold)[0]
        if len(inliers) > len(best_inliers):
            best_inliers = inliers
            best_plane = np.append(normal, d)
            if len(best_inliers) > 0.6 * N:
                break

    normal = best_plane[:3]
    d = float(best_plane[3])
    # Ensure normal points upwards relative to camera centroid
    return normal, d, best_inliers


def compute_rotation_matrix_to_y(normal: np.ndarray) -> np.ndarray:
    """Compute 3x3 rotation matrix that rotates vector `normal` into [0, 1, 0]."""
    target = np.array([0.0, 1.0, 0.0])
    v = np.cross(normal, target)
    s = np.linalg.norm(v)
    c = np.dot(normal, target)
    if s < 1e-6:
        # Already aligned or antiparallel
        if c > 0:
            return np.eye(3)
        else:
            # 180 flip around X
            return np.diag([1.0, -1.0, -1.0])
    vx = np.array([
        [0.0, -v[2], v[1]],
        [v[2], 0.0, -v[0]],
        [-v[1], v[0], 0.0]
    ])
    R = np.eye(3) + vx + (vx @ vx) * ((1.0 - c) / (s * s))
    return R


class AlignStage(BaseStage):
    def __init__(self):
        super().__init__(
            name="align",
            description="Fit dominant floor plane with RANSAC, rotate to Y-up, translate to y=0",
        )

    def is_cached(self, out_dir: Path, config: PipelineConfig) -> bool:
        aligned_json = out_dir / "aligned_poses.json"
        return aligned_json.exists()

    def execute(
        self,
        input_path: Path,
        out_dir: Path,
        config: PipelineConfig,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        poses_path = out_dir / "poses.json"
        if not poses_path.exists():
            raise RuntimeError(f"Poses manifest not found at {poses_path}")

        poses_data = json.loads(poses_path.read_text(encoding="utf-8"))
        frames = poses_data.get("frames", [])

        # Load 3D sparse points
        best_sparse = context.get("best_sparse", out_dir / "colmap" / "sparse" / "0")
        ply_candidates = list(out_dir.rglob("points3D.ply"))
        points = None
        if ply_candidates:
            mesh = trimesh.load(str(ply_candidates[0]))
            points = np.asarray(mesh.vertices)

        if points is None or len(points) == 0:
            # Fallback to camera centers
            positions = np.array([f["position"] for f in frames])
            points = positions

        # Focus RANSAC on the bottom 40% height of points (likely floor region)
        y_vals = points[:, 1]
        y_thresh = np.percentile(y_vals, config.floor_alignment.search_height_fraction * 100)
        floor_candidates = points[y_vals <= y_thresh]
        if len(floor_candidates) < 10:
            floor_candidates = points

        normal, d, inliers = fit_plane_ransac(
            floor_candidates,
            dist_threshold=config.floor_alignment.ransac_threshold_m,
            max_iters=config.floor_alignment.max_iterations,
        )

        # Ensure normal points toward the scene interior (+Y)
        cam_positions = np.array([f["position"] for f in frames])
        cam_centroid = np.mean(cam_positions, axis=0) if len(cam_positions) > 0 else np.zeros(3)
        if np.dot(normal, cam_centroid) + d < 0:
            normal = -normal
            d = -d

        R = compute_rotation_matrix_to_y(normal)

        # Apply rotation to points to find floor y
        rot_points = points @ R.T
        rot_floor_candidates = floor_candidates @ R.T
        floor_y = float(np.percentile(rot_floor_candidates[:, 1], 5))

        # Full 4x4 Transformation Matrix: T_align
        # 1. Rotate by R
        # 2. Shift Y by -floor_y (so floor is at y = 0.0)
        T_align = np.eye(4)
        T_align[:3, :3] = R
        T_align[1, 3] = -floor_y

        print(f"[INFO] Floor normal: {normal.round(3)}, distance: {d:.3f}")
        print(f"[INFO] Aligning floor: rotating normal to +Y, translating floor Y by {-floor_y:.3f}m -> 0.0m")

        # Transform all frames
        aligned_frames = []
        for f in frames:
            pos = np.array(f["position"])
            pos_h = np.append(pos, 1.0)
            new_pos = (T_align @ pos_h)[:3]

            # Invert transform on rotation if quaternion is stored
            qx, qy, qz, qw = f["rotation"]
            aligned_frames.append({
                **f,
                "position": [round(float(new_pos[0]), 4), round(float(new_pos[1]), 4), round(float(new_pos[2]), 4)],
            })

        aligned_manifest = {
            "meta": {
                "units": config.general.units,
                "up": "Y",
                "floor_y": 0.0,
                "scale_method": config.general.scale_method,
                "transform_matrix": T_align.tolist(),
            },
            "frames": aligned_frames,
        }

        aligned_out = out_dir / "aligned_poses.json"
        aligned_out.write_text(json.dumps(aligned_manifest, indent=2), encoding="utf-8")
        print(f"[OK] Saved canonical Y-up aligned poses -> {aligned_out}")

        context["aligned_poses"] = aligned_manifest
        context["T_align"] = T_align
        return context
