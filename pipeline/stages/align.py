"""
pipeline/stages/align.py
────────────────────────
Stage 3: RANSAC Floor Plane Fitting & Canonical Alignment.
Identifies the dominant horizontal floor plane below the camera trajectory,
rotates it so the normal is strictly +Y, and translates the floor to y = 0.0.
Transforms all camera poses and 3D geometry into the canonical Y-up metric frame.

Outputs:
- out/aligned_poses.json (canonical poses, Y-up, floor at y = 0)
- out/mesh/aligned_points.ply
- out/debug_floor_alignment.png (debug render proving flat floor at y = 0 and vertical walls)
"""

import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import matplotlib
matplotlib.use("Agg")  # Headless backend
import matplotlib.pyplot as plt
import numpy as np
from scipy.spatial.transform import Rotation
import trimesh

from .base import BaseStage
from ..config import PipelineConfig


def fit_plane_ransac(
    points: np.ndarray,
    cam_centroid: np.ndarray,
    dist_threshold: float = 0.05,
    max_iters: int = 3000,
) -> Tuple[np.ndarray, float, np.ndarray]:
    """
    Fit a dominant horizontal floor plane using RANSAC.
    Prioritizes planes whose normal points upward toward the camera centroid.
    """
    N = len(points)
    if N < 3:
        return np.array([0.0, 1.0, 0.0]), 0.0, np.arange(N)

    best_inliers = np.array([], dtype=int)
    best_normal = np.array([0.0, 1.0, 0.0])
    best_d = 0.0

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
        d = -float(np.dot(normal, p1))

        # Check inliers
        dists = np.abs(np.dot(points, normal) + d)
        inliers = np.where(dists < dist_threshold)[0]

        if len(inliers) > len(best_inliers):
            # Orient normal toward camera centroid
            test_val = float(np.dot(normal, cam_centroid) + d)
            oriented_normal = normal if test_val > 0 else -normal
            oriented_d = d if test_val > 0 else -d

            best_inliers = inliers
            best_normal = oriented_normal
            best_d = oriented_d

            if len(best_inliers) > 0.65 * N:
                break

    return best_normal, best_d, best_inliers


def compute_rotation_matrix_to_y(normal: np.ndarray) -> np.ndarray:
    """Compute 3x3 rotation matrix that rotates unit vector `normal` into [0, 1, 0]."""
    target = np.array([0.0, 1.0, 0.0])
    v = np.cross(normal, target)
    s = np.linalg.norm(v)
    c = float(np.dot(normal, target))
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


def render_alignment_debug(
    aligned_points: np.ndarray,
    aligned_cams: np.ndarray,
    inlier_mask: np.ndarray,
    out_png: Path,
):
    """
    Render 3-panel debug visualization verifying floor is flat at y=0 and walls vertical.
    """
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 3, figsize=(18, 5))
    fig.patch.set_facecolor("#1e1e1e")

    # Downsample points for clear rendering
    n_pts = len(aligned_points)
    idx_sample = np.random.choice(n_pts, min(n_pts, 8000), replace=False)
    pts = aligned_points[idx_sample]

    inlier_pts = aligned_points[inlier_mask] if len(inlier_mask) > 0 else np.zeros((0, 3))
    if len(inlier_pts) > 2000:
        idx_inliers = np.random.choice(len(inlier_pts), 2000, replace=False)
        inlier_pts = inlier_pts[idx_inliers]

    cams = aligned_cams

    for ax in axes:
        ax.set_facecolor("#121212")
        ax.tick_params(colors="#aaaaaa")
        ax.grid(True, color="#333333", linestyle="--", linewidth=0.5)

    # 1. Side View: Z vs Y (Elevation)
    ax0 = axes[0]
    ax0.scatter(pts[:, 2], pts[:, 1], c="#5588cc", s=1.5, alpha=0.4, label="Scene Points")
    if len(inlier_pts) > 0:
        ax0.scatter(inlier_pts[:, 2], inlier_pts[:, 1], c="#22cc66", s=3, alpha=0.8, label="Floor Inliers")
    ax0.plot(cams[:, 2], cams[:, 1], "-o", color="#ffaa00", markersize=4, linewidth=1.5, label="Camera Path")
    ax0.axhline(0.0, color="#ff4444", linestyle="--", linewidth=2.0, label="Floor (y = 0.0m)")
    ax0.set_xlabel("Z (metres)", color="#ffffff")
    ax0.set_ylabel("Y - Elevation (metres)", color="#ffffff")
    ax0.set_title("Side Elevation (Z vs Y)\n[Verifies Floor Flat at y=0 & Vertical Walls]", color="#ffffff", fontsize=11)
    ax0.legend(loc="upper right", facecolor="#222222", edgecolor="#444444", labelcolor="#ffffff", fontsize=8)

    # 2. Front View: X vs Y (Elevation)
    ax1 = axes[1]
    ax1.scatter(pts[:, 0], pts[:, 1], c="#5588cc", s=1.5, alpha=0.4)
    if len(inlier_pts) > 0:
        ax1.scatter(inlier_pts[:, 0], inlier_pts[:, 1], c="#22cc66", s=3, alpha=0.8)
    ax1.plot(cams[:, 0], cams[:, 1], "-o", color="#ffaa00", markersize=4, linewidth=1.5)
    ax1.axhline(0.0, color="#ff4444", linestyle="--", linewidth=2.0)
    ax1.set_xlabel("X (metres)", color="#ffffff")
    ax1.set_ylabel("Y - Elevation (metres)", color="#ffffff")
    ax1.set_title("Front Elevation (X vs Y)\n[Verifies Horizon & Orthogonality]", color="#ffffff", fontsize=11)

    # 3. Top-Down View: X vs Z (Plan View / Floorplan)
    ax2 = axes[2]
    ax2.scatter(pts[:, 0], pts[:, 2], c="#5588cc", s=1.5, alpha=0.4)
    ax2.plot(cams[:, 0], cams[:, 2], "-o", color="#ffaa00", markersize=4, linewidth=1.5, label="Camera Path")
    ax2.scatter([cams[0, 0]], [cams[0, 2]], color="#00ffcc", s=50, zorder=5, label="Start")
    ax2.set_xlabel("X (metres)", color="#ffffff")
    ax2.set_ylabel("Z (metres)", color="#ffffff")
    ax2.set_title("Top-Down Floorplan (X vs Z)\n[Verifies Scene Footprint & Trajectory]", color="#ffffff", fontsize=11)
    ax2.legend(loc="upper right", facecolor="#222222", edgecolor="#444444", labelcolor="#ffffff", fontsize=8)

    plt.tight_layout()
    plt.savefig(str(out_png), dpi=150, facecolor=fig.get_facecolor())
    plt.close()
    print(f"[OK] Floor alignment debug render saved -> {out_png}")


def write_points_ply(points: List[Dict[str, Any]], out_path: Path):
    """Export points to standard ASCII PLY."""
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
    """
    Milestone M2: Floor Plane Alignment.
    Enforces canonical coordinate frame: Y-up, metres, floor at y = 0.0.
    """

    def __init__(self):
        super().__init__(
            name="align",
            description="Fit dominant floor plane with RANSAC, rotate to Y-up, translate to y=0",
        )

    def is_cached(self, out_dir: Path, config: PipelineConfig) -> bool:
        aligned_json = out_dir / "aligned_poses.json"
        debug_png = out_dir / "debug_floor_alignment.png"
        return aligned_json.exists() and debug_png.exists()

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

        # Load 3D point cloud
        points = None
        if sparse_points and len(sparse_points) > 0:
            points = np.array([p["xyz"] for p in sparse_points])
        else:
            ply_candidates = list(out_dir.rglob("points3D.ply"))
            if ply_candidates:
                mesh = trimesh.load(str(ply_candidates[0]))
                points = np.asarray(mesh.vertices)

        cam_positions = np.array([f["position"] for f in frames])
        if len(cam_positions) == 0:
            raise RuntimeError("No camera frames found in poses.json.")

        cam_centroid = np.mean(cam_positions, axis=0)

        if points is None or len(points) == 0:
            points = cam_positions

        # Select candidate floor points below camera trajectory centroid
        # In indoor capture, the camera is held at eye/chest level; the floor is below it.
        y_cams_median = float(np.median(cam_positions[:, 1]))
        floor_candidates = points[points[:, 1] <= y_cams_median]
        if len(floor_candidates) < 30:
            # Fallback to bottom 40% of point cloud
            y_thresh = np.percentile(points[:, 1], config.floor_alignment.search_height_fraction * 100)
            floor_candidates = points[points[:, 1] <= y_thresh]
        if len(floor_candidates) < 10:
            floor_candidates = points

        normal, d, inliers = fit_plane_ransac(
            floor_candidates,
            cam_centroid=cam_centroid,
            dist_threshold=config.floor_alignment.ransac_threshold_m,
            max_iters=config.floor_alignment.max_iterations,
        )

        R = compute_rotation_matrix_to_y(normal)

        # Rotate points to determine floor Y intercept
        inlier_points = floor_candidates[inliers] if len(inliers) > 0 else floor_candidates
        rot_inliers = inlier_points @ R.T
        floor_y = float(np.median(rot_inliers[:, 1])) if len(rot_inliers) > 0 else 0.0

        # Construct canonical 4x4 Transformation Matrix: T_align
        # 1. Rotate by R (so floor normal aligns with +Y)
        # 2. Translate along Y by -floor_y (so floor plane is at y = 0.0)
        T_align = np.eye(4)
        T_align[:3, :3] = R
        T_align[1, 3] = -floor_y

        print(f"[INFO] Dominant floor normal: {normal.round(4)}, plane d: {d:.4f}")
        print(f"[INFO] Aligning floor: rotating normal to +Y, translating floor Y by {-floor_y:.4f}m -> 0.0m")

        # Transform all camera frames
        aligned_frames = []
        aligned_cams = []
        for f in frames:
            pos = np.array(f["position"])
            pos_h = np.append(pos, 1.0)
            new_pos = (T_align @ pos_h)[:3]
            aligned_cams.append(new_pos)

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

        aligned_cams = np.array(aligned_cams)

        # Transform all sparse 3D points
        aligned_sparse_points = []
        aligned_pts_arr = []
        for pt in sparse_points:
            pt_pos = np.append(np.array(pt["xyz"]), 1.0)
            new_xyz = (T_align @ pt_pos)[:3]
            aligned_pts_arr.append(new_xyz)
            aligned_sparse_points.append({
                **pt,
                "xyz": [round(float(c), 4) for c in new_xyz],
            })

        aligned_pts_arr = np.array(aligned_pts_arr) if aligned_pts_arr else (points @ R.T + np.array([0, -floor_y, 0]))

        # Calculate floor flatness statistics on inliers
        inlier_rot = (inlier_points @ R.T) + np.array([0, -floor_y, 0])
        floor_residuals = inlier_rot[:, 1]
        mean_floor_y = float(np.mean(floor_residuals))
        std_floor_y = float(np.std(floor_residuals))
        print(f"[INFO] Floor inliers: {len(inlier_rot)} points | Mean y = {mean_floor_y:.4f}m, StdDev = {std_floor_y:.4f}m (Target: 0.000m)")

        # Render debug visualization
        debug_png = out_dir / "debug_floor_alignment.png"
        render_alignment_debug(
            aligned_points=aligned_pts_arr,
            aligned_cams=aligned_cams,
            inlier_mask=inliers,
            out_png=debug_png,
        )

        aligned_manifest = {
            "meta": {
                "units": config.general.units,
                "up": "Y",
                "floor_y": 0.0,
                "scale_method": poses_data.get("scale_method", config.general.scale_method),
                "scale_factor": poses_data.get("scale_factor", 1.0),
                "transform_matrix": T_align.tolist(),
                "floor_flatness_std_m": round(std_floor_y, 4),
            },
            "frames": aligned_frames,
            "sparse_points": aligned_sparse_points,
        }

        aligned_out = out_dir / "aligned_poses.json"
        aligned_out.write_text(json.dumps(aligned_manifest, indent=2), encoding="utf-8")
        print(f"[OK] Saved canonical Y-up aligned poses -> {aligned_out}")

        # Save aligned PLY
        aligned_ply_path = out_dir / "mesh" / "aligned_points.ply"
        write_points_ply(aligned_sparse_points, aligned_ply_path)

        context["aligned_poses"] = aligned_manifest
        context["T_align"] = T_align
        return context
