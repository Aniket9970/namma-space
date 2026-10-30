"""
pipeline/stages/align.py
────────────────────────
Stage 3: RANSAC Floor Plane Fitting & Coordinate Alignment.
Identifies the dominant floor plane, rotates it to Y-up (+Y), and translates floor to y = 0.
Transforms all camera poses and landmark points into the canonical metric frame.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple
import numpy as np
from scipy.spatial.transform import Rotation
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
    return normal, d, best_inliers


def compute_rotation_matrix_to_y(normal: np.ndarray) -> np.ndarray:
    """Compute 3x3 rotation matrix that rotates vector `normal` into [0, 1, 0]."""
    target = np.array([0.0, 1.0, 0.0])
    v = np.cross(normal, target)
    s = np.linalg.norm(v)
    c = np.dot(normal, target)
    if s < 1e-6:
        if c > 0:
            return np.eye(3)
        else:
            return np.diag([1.0, -1.0, -1.0])
    vx = np.array([
        [0.0, -v[2], v[1]],
        [v[2], 0.0, -v[0]],
        [-v[1], v[0], 0.0]
    ])
    R = np.eye(3) + vx + (vx @ vx) * ((1.0 - c) / (s * s))
    return R


def write_points_ply(points: List[Dict[str, Any]], out_path: Path):
    """Export points to ASCII PLY."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    header = [
        "ply",
        "format ascii 1.0",
        f"element vertex {len(points)}",
        "property float x",
        "property float y",
        "property float z",
        "property uchar red",
        "property uchar green",
        "property uchar blue",
        "end_header\n",
    ]
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(header))
        for pt in points:
            x, y, z = pt["xyz"]
            r, g, b = pt.get("rgb", [180, 180, 180])
            f.write(f"{x:.4f} {y:.4f} {z:.4f} {r} {g} {b}\n")


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
        sparse_points = poses_data.get("sparse_points", [])

        # Load 3D sparse points
        points = None
        if sparse_points and len(sparse_points) > 0:
            points = np.array([p["xyz"] for p in sparse_points])
        else:
            ply_candidates = list(out_dir.rglob("points3D.ply"))
            if ply_candidates:
                mesh = trimesh.load(str(ply_candidates[0]))
                points = np.asarray(mesh.vertices)

        if points is None or len(points) == 0:
            positions = np.array([f["position"] for f in frames])
            points = positions

        # Focus RANSAC on the bottom fraction of height (floor region)
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

        # Ensure normal points toward scene interior (+Y)
        cam_positions = np.array([f["position"] for f in frames])
        cam_centroid = np.mean(cam_positions, axis=0) if len(cam_positions) > 0 else np.zeros(3)
        if np.dot(normal, cam_centroid) + d < 0:
            normal = -normal
            d = -d

        R = compute_rotation_matrix_to_y(normal)

        # Apply rotation to points to find floor y
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

        # Transform all frames (both position and camera rotation quaternion)
        aligned_frames = []
        for f in frames:
            pos = np.array(f["position"])
            pos_h = np.append(pos, 1.0)
            new_pos = (T_align @ pos_h)[:3]

            # Rotate camera orientation quaternion: R_new = R @ R_old
            qx, qy, qz, qw = f["rotation"]
            try:
                rot_old = Rotation.from_quat([qx, qy, qz, qw]).as_matrix()
                rot_new = R @ rot_old
                new_quat = Rotation.from_matrix(rot_new).as_quat()
                new_rot = [round(float(c), 6) for c in new_quat]
            except Exception:
                new_rot = [qx, qy, qz, qw]

            aligned_frames.append({
                **f,
                "position": [round(float(new_pos[0]), 4), round(float(new_pos[1]), 4), round(float(new_pos[2]), 4)],
                "rotation": new_rot,
            })

        # Transform sparse points
        aligned_sparse_points = []
        for pt in sparse_points:
            pt_pos = np.append(np.array(pt["xyz"]), 1.0)
            new_xyz = (T_align @ pt_pos)[:3]
            aligned_sparse_points.append({
                **pt,
                "xyz": [round(float(c), 4) for c in new_xyz],
            })

        aligned_manifest = {
            "meta": {
                "units": config.general.units,
                "up": "Y",
                "floor_y": 0.0,
                "scale_method": poses_data.get("scale_method", config.general.scale_method),
                "scale_factor": poses_data.get("scale_factor", 1.0),
                "transform_matrix": T_align.tolist(),
            },
            "frames": aligned_frames,
            "sparse_points": aligned_sparse_points,
        }

        aligned_out = out_dir / "aligned_poses.json"
        aligned_out.write_text(json.dumps(aligned_manifest, indent=2), encoding="utf-8")
        print(f"[OK] Saved canonical Y-up aligned poses -> {aligned_out}")

        # Also write aligned PLY for visualization and debug
        if aligned_sparse_points:
            aligned_ply_path = out_dir / "mesh" / "aligned_points.ply"
            write_points_ply(aligned_sparse_points, aligned_ply_path)

        context["aligned_poses"] = aligned_manifest
        context["T_align"] = T_align
        return context
