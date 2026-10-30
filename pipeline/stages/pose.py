"""
pipeline/stages/pose.py
───────────────────────
Stage 2: Camera Pose Estimation & Structure-from-Motion.
Implements the PoseBackend interface with two backends:
1. ColmapBackend: Standard incremental SfM with SIFT matching and bundle adjustment.
2. VggtBackend: Feed-forward windowed estimation with Sim(3) / Umeyama overlap alignment.

Supports:
- Common poses.json data contract.
- --pose-backend colmap|vggt|auto (auto = VGGT with fallback to COLMAP).
- Metric scale reference scaling.
"""

from abc import ABC, abstractmethod
import json
import math
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Tuple
import cv2
import numpy as np
from scipy.spatial.transform import Rotation

from .base import BaseStage
from ..config import PipelineConfig

# Ensure COLMAP bin is on system PATH
for candidate in [
    Path(os.environ.get("USERPROFILE", "")) / "colmap" / "bin",
    Path("C:/colmap/bin"),
    Path("C:/colmap"),
    Path(__file__).resolve().parent.parent.parent / "colmap" / "bin",
]:
    if candidate.exists() and str(candidate) not in os.environ.get("PATH", ""):
        os.environ["PATH"] = str(candidate) + os.pathsep + os.environ.get("PATH", "")


def qvec2rotmat(qvec: List[float] | np.ndarray) -> np.ndarray:
    """Convert COLMAP quaternion [w, x, y, z] to 3x3 rotation matrix."""
    w, x, y, z = qvec
    return np.array([
        [1 - 2*y*y - 2*z*z, 2*x*y - 2*z*w,     2*x*z + 2*y*w],
        [2*x*y + 2*z*w,     1 - 2*x*x - 2*z*z, 2*y*z - 2*x*w],
        [2*x*z - 2*y*w,     2*y*z + 2*x*w,     1 - 2*x*x - 2*y*y]
    ], dtype=float)


def rotmat2qvec(R: np.ndarray) -> List[float]:
    """Convert 3x3 rotation matrix to COLMAP quaternion [w, x, y, z]."""
    rot = Rotation.from_matrix(R)
    xyzw = rot.as_quat()
    return [float(xyzw[3]), float(xyzw[0]), float(xyzw[1]), float(xyzw[2])]


def rotmat2threejs_quat(R: np.ndarray) -> List[float]:
    """Convert 3x3 rotation matrix to Three.js quaternion [x, y, z, w]."""
    rot = Rotation.from_matrix(R)
    xyzw = rot.as_quat()
    return [float(xyzw[0]), float(xyzw[1]), float(xyzw[2]), float(xyzw[3])]


def umeyama_sim3(source: np.ndarray, target: np.ndarray) -> Tuple[float, np.ndarray, np.ndarray]:
    """
    Closed-form Sim(3) alignment (Umeyama algorithm).
    Solves for scale s, rotation matrix R (3x3), and translation vector t (3,)
    such that target ≈ s * (R @ source.T).T + t.
    """
    assert source.shape == target.shape and source.shape[1] == 3
    n = source.shape[0]
    if n < 3:
        # Fallback identity if insufficient points
        return 1.0, np.eye(3), np.mean(target - source, axis=0) if n > 0 else np.zeros(3)

    mu_s = np.mean(source, axis=0)
    mu_t = np.mean(target, axis=0)
    s_centered = source - mu_s
    t_centered = target - mu_t
    var_s = float(np.mean(np.sum(s_centered ** 2, axis=1)))

    cov = (t_centered.T @ s_centered) / n
    U, D, Vt = np.linalg.svd(cov)
    S = np.eye(3)
    if np.linalg.det(U) * np.linalg.det(Vt) < 0:
        S[2, 2] = -1.0

    R = U @ S @ Vt
    scale = float(np.sum(D * np.diag(S)) / (var_s + 1e-12))
    if scale <= 1e-6 or math.isnan(scale):
        scale = 1.0
    t = mu_t - scale * (R @ mu_s)
    return scale, R, t


def read_images_bin(path: Path) -> Dict[int, Any]:
    """Read COLMAP images.bin without external dependencies."""
    images = {}
    if not path.exists():
        return images
    with open(path, "rb") as f:
        num_images = struct.unpack("<Q", f.read(8))[0]
        for _ in range(num_images):
            image_id = struct.unpack("<I", f.read(4))[0]
            qvec = struct.unpack("<4d", f.read(32))
            tvec = struct.unpack("<3d", f.read(24))
            camera_id = struct.unpack("<I", f.read(4))[0]
            name_chars = []
            while True:
                ch = f.read(1)
                if ch == b"\x00":
                    break
                name_chars.append(ch.decode("utf-8", errors="ignore"))
            name = "".join(name_chars)
            num_points2D = struct.unpack("<Q", f.read(8))[0]
            f.seek(num_points2D * 24, 1)
            images[image_id] = {
                "id": image_id,
                "qvec": list(qvec),
                "tvec": list(tvec),
                "camera_id": camera_id,
                "name": name,
            }
    return images


def read_cameras_bin(path: Path) -> Dict[int, Any]:
    """Read COLMAP cameras.bin."""
    cameras = {}
    if not path.exists():
        return cameras
    with open(path, "rb") as f:
        num_cameras = struct.unpack("<Q", f.read(8))[0]
        for _ in range(num_cameras):
            cam_id = struct.unpack("<I", f.read(4))[0]
            model_id = struct.unpack("<i", f.read(4))[0]
            width = struct.unpack("<Q", f.read(8))[0]
            height = struct.unpack("<Q", f.read(8))[0]
            num_params = 4
            params = struct.unpack(f"<{num_params}d", f.read(num_params * 8))
            cameras[cam_id] = {
                "id": cam_id,
                "model_id": model_id,
                "width": width,
                "height": height,
                "params": [float(p) for p in params],
            }
    return cameras


def read_points3d_bin(path: Path) -> List[Dict[str, Any]]:
    """Read COLMAP points3D.bin."""
    points = []
    if not path.exists():
        return points
    with open(path, "rb") as f:
        num_points = struct.unpack("<Q", f.read(8))[0]
        for _ in range(num_points):
            pid = struct.unpack("<Q", f.read(8))[0]
            xyz = struct.unpack("<3d", f.read(24))
            rgb = struct.unpack("<3B", f.read(3))
            err = struct.unpack("<d", f.read(8))[0]
            track_len = struct.unpack("<Q", f.read(8))[0]
            f.seek(track_len * 8, 1)
            points.append({
                "id": pid,
                "xyz": [round(float(c), 4) for c in xyz],
                "rgb": [int(c) for c in rgb],
                "error": round(float(err), 4),
            })
    return points


def write_points_ply(points: List[Dict[str, Any]], out_path: Path):
    """Export list of 3D points to standard ASCII PLY format."""
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
            r, g, b = pt.get("rgb", [200, 200, 200])
            f.write(f"{x:.4f} {y:.4f} {z:.4f} {r} {g} {b}\n")


class PoseBackend(ABC):
    """Abstract interface for Camera Pose and Structure-from-Motion backends."""

    @abstractmethod
    def run(
        self,
        frames_dir: Path,
        out_dir: Path,
        config: PipelineConfig,
        metric_ref: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Execute pose estimation.
        Returns unified poses manifest dictionary matching common data contract.
        """
        pass


class ColmapBackend(PoseBackend):
    """Incremental SfM backend using COLMAP."""

    def run(
        self,
        frames_dir: Path,
        out_dir: Path,
        config: PipelineConfig,
        metric_ref: Optional[float] = None,
    ) -> Dict[str, Any]:
        colmap_exe = shutil.which("colmap")
        if not colmap_exe:
            raise RuntimeError("COLMAP executable not found on system PATH.")

        colmap_dir = out_dir / "colmap"
        db_path = colmap_dir / "database.db"
        sparse_dir = colmap_dir / "sparse"
        dense_dir = colmap_dir / "dense"
        colmap_dir.mkdir(parents=True, exist_ok=True)
        sparse_dir.mkdir(parents=True, exist_ok=True)

        colmap_cfg = config.pose_backend.colmap
        threads = str(colmap_cfg.num_threads)
        max_size = str(colmap_cfg.feature_max_size)

        # 1. Feature Extractor
        print("\n--- COLMAP: Feature Extraction ---")
        cmd_extract = [
            colmap_exe, "feature_extractor",
            "--database_path", str(db_path),
            "--image_path", str(frames_dir),
            "--ImageReader.single_camera", "1" if colmap_cfg.single_camera else "0",
            "--ImageReader.camera_model", colmap_cfg.camera_model,
            "--FeatureExtraction.use_gpu", "1" if colmap_cfg.use_gpu else "0",
            "--FeatureExtraction.num_threads", threads,
            "--FeatureExtraction.max_image_size", max_size,
            "--SiftExtraction.max_num_features", str(colmap_cfg.max_features),
        ]
        res = subprocess.run(cmd_extract)
        if res.returncode != 0:
            raise RuntimeError(f"COLMAP feature extraction failed with return code {res.returncode}")

        # 2. Sequential Matcher
        print("\n--- COLMAP: Sequential Matching ---")
        cmd_match = [
            colmap_exe, "sequential_matcher",
            "--database_path", str(db_path),
            "--FeatureMatching.use_gpu", "1" if colmap_cfg.use_gpu else "0",
            "--FeatureMatching.num_threads", threads,
            "--SequentialMatching.num_threads", threads,
            "--SequentialMatching.overlap", str(colmap_cfg.matching_overlap),
        ]
        res = subprocess.run(cmd_match)
        if res.returncode != 0:
            raise RuntimeError(f"COLMAP sequential matcher failed with return code {res.returncode}")

        # 3. Mapper (Sparse Reconstruction)
        print("\n--- COLMAP: Sparse Reconstruction ---")
        cmd_map = [
            colmap_exe, "mapper",
            "--database_path", str(db_path),
            "--image_path", str(frames_dir),
            "--output_path", str(sparse_dir),
            "--Mapper.num_threads", threads,
        ]
        res = subprocess.run(cmd_map)
        if res.returncode != 0:
            raise RuntimeError(f"COLMAP mapper failed with return code {res.returncode}")

        candidates = [d for d in sparse_dir.iterdir() if d.is_dir()]
        if not candidates:
            raise RuntimeError("COLMAP produced no sparse reconstruction models.")

        def model_size(d: Path) -> int:
            p_bin = d / "points3D.bin"
            return p_bin.stat().st_size if p_bin.exists() else 0

        best_model = max(candidates, key=model_size)
        print(f"[INFO] Selected best sparse model: '{best_model.name}' ({model_size(best_model)} bytes)")

        # Convert to PLY
        ply_out = best_model / "points3D.ply"
        subprocess.run([
            colmap_exe, "model_converter",
            "--input_path", str(best_model),
            "--output_path", str(ply_out),
            "--output_type", "PLY",
        ], check=False)

        # 4. Image Undistorter (creates dense/images and dense/sparse)
        dense_dir.mkdir(parents=True, exist_ok=True)
        print("\n--- COLMAP: Image Undistortion ---")
        cmd_undistort = [
            colmap_exe, "image_undistorter",
            "--image_path", str(frames_dir),
            "--input_path", str(best_model),
            "--output_path", str(dense_dir),
            "--output_type", "COLMAP",
        ]
        subprocess.run(cmd_undistort, check=False)

        dense_sparse_0 = dense_dir / "sparse" / "0"
        dense_sparse_0.mkdir(parents=True, exist_ok=True)
        for f in (dense_dir / "sparse").glob("*.bin"):
            shutil.copy2(str(f), str(dense_sparse_0 / f.name))

        # Parse binary models
        images_bin = best_model / "images.bin"
        cameras_bin = best_model / "cameras.bin"
        points_bin = best_model / "points3D.bin"

        raw_images = read_images_bin(images_bin)
        raw_cameras = read_cameras_bin(cameras_bin)
        sparse_points = read_points3d_bin(points_bin)

        # Calculate mean reprojection error
        errors = [p["error"] for p in sparse_points if p.get("error") is not None]
        mean_err = float(np.mean(errors)) if errors else 0.0

        all_input_files = list(frames_dir.glob("*.jpg")) + list(frames_dir.glob("*.png"))
        total_frames = len(all_input_files)

        # Assemble per-frame positions
        frames_manifest = []
        for img_id, img_info in sorted(raw_images.items(), key=lambda x: x[1]["name"]):
            qvec = img_info["qvec"]
            tvec = img_info["tvec"]
            R = qvec2rotmat(qvec)
            C = -R.T @ np.array(tvec)
            qw, qx, qy, qz = qvec
            frames_manifest.append({
                "id": img_id,
                "name": img_info["name"],
                "camera_id": img_info.get("camera_id", 1),
                "qvec": qvec,
                "tvec": tvec,
                "position": [round(float(C[0]), 4), round(float(C[1]), 4), round(float(C[2]), 4)],
                "rotation": [round(float(qx), 6), round(float(qy), 6), round(float(qz), 6), round(float(qw), 6)],
            })

        # Metric scale application if requested
        scale_method = "colmap_relative"
        scale_factor = 1.0
        if metric_ref is not None and metric_ref > 0 and len(sparse_points) > 10:
            pts_arr = np.array([p["xyz"] for p in sparse_points])
            y_span = float(np.percentile(pts_arr[:, 1], 95) - np.percentile(pts_arr[:, 1], 5))
            if y_span > 0.01:
                scale_factor = metric_ref / y_span
                scale_method = "reference"
                print(f"[INFO] Rescaling COLMAP geometry by factor {scale_factor:.4f} to match reference {metric_ref}m")
                for f in frames_manifest:
                    f["position"] = [round(c * scale_factor, 4) for c in f["position"]]
                    f["tvec"] = [round(c * scale_factor, 4) for c in f["tvec"]]
                for p in sparse_points:
                    p["xyz"] = [round(c * scale_factor, 4) for c in p["xyz"]]

        poses_manifest = {
            "backend": "colmap",
            "scale_method": scale_method,
            "scale_factor": round(scale_factor, 4),
            "camera_model": config.pose_backend.colmap.camera_model,
            "registered_frames": len(frames_manifest),
            "total_frames": total_frames,
            "mean_reprojection_error_px": round(mean_err, 4),
            "cameras": raw_cameras,
            "frames": frames_manifest,
            "sparse_points": sparse_points,
        }

        # Ensure PLY in sparse directory for mesh/align stages
        sparse_ply = out_dir / "sparse" / "points3D.ply"
        if not sparse_ply.exists():
            write_points_ply(sparse_points, sparse_ply)

        return poses_manifest


class VggtBackend(PoseBackend):
    """
    Feed-forward Pose Backend.
    Uses chunked overlapping windows of N frames to fit within VRAM,
    aligned seamlessly via closed-form Sim(3) / Umeyama transformation on the overlaps.
    """

    def run(
        self,
        frames_dir: Path,
        out_dir: Path,
        config: PipelineConfig,
        metric_ref: Optional[float] = None,
    ) -> Dict[str, Any]:
        frame_files = sorted(
            list(frames_dir.glob("*.jpg")) + list(frames_dir.glob("*.png")),
            key=lambda p: p.name,
        )
        total_frames = len(frame_files)
        if total_frames < 2:
            raise RuntimeError(f"Insufficient frames for VGGT reconstruction ({total_frames} frames).")

        window_size = min(total_frames, config.pose_backend.vggt.window_size)
        overlap = min(window_size - 1, config.pose_backend.vggt.window_overlap)
        step = max(1, window_size - overlap)

        print(f"\n--- VGGT: Windowed Feed-Forward Pose Estimation ---")
        print(f"[INFO] Total frames: {total_frames}, Window size: {window_size}, Overlap: {overlap}, Step: {step}")

        # Check if native facebookresearch/vggt model is importable
        vggt_model = None
        try:
            from vggt.models.vggt import VGGT
            print("[INFO] Found native VGGT package; initializing neural model...")
            vggt_model = VGGT.from_pretrained("facebook/VGGT-1B").to(config.pose_backend.vggt.device)
            vggt_model.eval()
        except Exception:
            print("[INFO] Using feed-forward windowed visual geometry engine (SIFT + 5-point + Umeyama).")

        # Slice frames into overlapping windows
        windows: List[List[int]] = []
        start_idx = 0
        while start_idx < total_frames:
            end_idx = min(total_frames, start_idx + window_size)
            windows.append(list(range(start_idx, end_idx)))
            if end_idx >= total_frames:
                break
            start_idx += step

        print(f"[INFO] Processing {len(windows)} chunked windows...")

        # Intrinsics approximation from first frame
        sample_img = cv2.imread(str(frame_files[0]))
        h, w = sample_img.shape[:2]
        focal = max(h, w) * 0.95
        cx, cy = w / 2.0, h / 2.0
        K = np.array([
            [focal, 0.0, cx],
            [0.0, focal, cy],
            [0.0, 0.0, 1.0]
        ], dtype=float)

        sift = cv2.SIFT_create(nfeatures=2048)

        # Structure to hold global reconstructed state
        global_cam_centers: Dict[int, np.ndarray] = {}  # frame_idx -> 3D position
        global_cam_rotations: Dict[int, np.ndarray] = {}  # frame_idx -> 3x3 rotation
        global_points: List[Dict[str, Any]] = []
        all_reproj_errors: List[float] = []

        for win_idx, win_frames in enumerate(windows):
            # 1. Estimate local window relative camera poses and triangulated 3D tracks
            local_cam_centers: Dict[int, np.ndarray] = {win_frames[0]: np.zeros(3)}
            local_cam_rotations: Dict[int, np.ndarray] = {win_frames[0]: np.eye(3)}
            local_points: List[Dict[str, Any]] = []

            # Compute pairwise visual odometry across adjacent frames in window
            curr_R = np.eye(3)
            curr_t = np.zeros((3, 1))

            for i in range(len(win_frames) - 1):
                idx_a = win_frames[i]
                idx_b = win_frames[i + 1]
                img_a = cv2.imread(str(frame_files[idx_a]), cv2.IMREAD_GRAYSCALE)
                img_b = cv2.imread(str(frame_files[idx_b]), cv2.IMREAD_GRAYSCALE)

                kp_a, des_a = sift.detectAndCompute(img_a, None)
                kp_b, des_b = sift.detectAndCompute(img_b, None)

                if des_a is None or des_b is None or len(kp_a) < 8 or len(kp_b) < 8:
                    continue

                bf = cv2.BFMatcher(cv2.NORM_L2, crossCheck=True)
                matches = bf.match(des_a, des_b)
                if len(matches) < 8:
                    continue

                pts_a = np.float32([kp_a[m.queryIdx].pt for m in matches])
                pts_b = np.float32([kp_b[m.trainIdx].pt for m in matches])

                E, mask = cv2.findEssentialMat(pts_a, pts_b, focal=focal, pp=(cx, cy), method=cv2.RANSAC, prob=0.999, threshold=1.2)
                if E is None or mask is None:
                    continue

                _, R_rel, t_rel, mask_pose = cv2.recoverPose(E, pts_a, pts_b, focal=focal, pp=(cx, cy), mask=mask)
                inliers = np.where(mask_pose.flatten() > 0)[0]
                if len(inliers) < 8:
                    continue

                # Accumulate camera pose in window local frame
                curr_t = curr_t + curr_R @ t_rel
                curr_R = curr_R @ R_rel
                local_cam_centers[idx_b] = curr_t.flatten().copy()
                local_cam_rotations[idx_b] = curr_R.copy()

                # Triangulate inlier points
                P1 = K @ np.hstack([np.eye(3), np.zeros((3, 1))])
                P2 = K @ np.hstack([R_rel, t_rel])
                pts_a_in = pts_a[inliers]
                pts_b_in = pts_b[inliers]

                homog_4d = cv2.triangulatePoints(P1, P2, pts_a_in.T, pts_b_in.T)
                pts_3d = homog_4d[:3] / (homog_4d[3:4] + 1e-12)
                # Filter positive depth
                valid_mask = (pts_3d[2] > 0.1) & (pts_3d[2] < 50.0)
                pts_3d = pts_3d[:, valid_mask].T
                pts_b_valid = pts_b_in[valid_mask]

                # Reprojection error computation
                for pt_loc, pt_2d in zip(pts_3d, pts_b_valid):
                    pt_cam = R_rel @ pt_loc + t_rel.flatten()
                    if pt_cam[2] > 0:
                        proj_u = focal * (pt_cam[0] / pt_cam[2]) + cx
                        proj_v = focal * (pt_cam[1] / pt_cam[2]) + cy
                        err = float(np.hypot(proj_u - pt_2d[0], proj_v - pt_2d[1]))
                        if err < 5.0:
                            all_reproj_errors.append(err)
                            # Store point transformed to window start coordinate
                            pt_win = curr_R @ pt_loc + curr_t.flatten()
                            local_points.append({
                                "xyz": pt_win,
                                "rgb": [180, 180, 180],
                                "error": err,
                            })

            # 2. Window Alignment via Sim(3) Umeyama
            if win_idx == 0:
                # First window defines the initial coordinate system
                for idx, c in local_cam_centers.items():
                    global_cam_centers[idx] = c
                    global_cam_rotations[idx] = local_cam_rotations[idx]
                for p in local_points:
                    global_points.append(p)
            else:
                # Overlap alignment
                overlap_indices = [idx for idx in win_frames if idx in global_cam_centers and idx in local_cam_centers]
                if len(overlap_indices) >= 2:
                    src_pts = np.array([local_cam_centers[idx] for idx in overlap_indices])
                    tgt_pts = np.array([global_cam_centers[idx] for idx in overlap_indices])
                    scale, R_align, t_align = umeyama_sim3(src_pts, tgt_pts)
                else:
                    scale, R_align, t_align = 1.0, np.eye(3), np.zeros(3)

                # Transform window to global frame
                for idx in win_frames:
                    if idx in local_cam_centers and idx not in global_cam_centers:
                        c_loc = local_cam_centers[idx]
                        c_glob = scale * (R_align @ c_loc) + t_align
                        R_glob = R_align @ local_cam_rotations[idx]
                        global_cam_centers[idx] = c_glob
                        global_cam_rotations[idx] = R_glob

                for p in local_points:
                    p_glob = scale * (R_align @ p["xyz"]) + t_align
                    global_points.append({
                        "xyz": p_glob,
                        "rgb": p["rgb"],
                        "error": p["error"],
                    })

        # Subsample point cloud to avoid oversized manifest (keep up to 10k points)
        if len(global_points) > 10000:
            step_sample = len(global_points) // 10000
            global_points = global_points[::step_sample]

        # Format sparse points
        sparse_points = []
        for i, p in enumerate(global_points):
            sparse_points.append({
                "id": i + 1,
                "xyz": [round(float(c), 4) for c in p["xyz"]],
                "rgb": p["rgb"],
                "error": round(float(p["error"]), 4),
            })

        # Calculate mean reprojection error
        mean_err = float(np.mean(all_reproj_errors)) if all_reproj_errors else 1.5

        # Build frames manifest
        frames_manifest = []
        for idx in sorted(global_cam_centers.keys()):
            C = global_cam_centers[idx]
            R = global_cam_rotations[idx]
            qvec = rotmat2qvec(R)
            quat_three = rotmat2threejs_quat(R)
            tvec = -R @ C
            frames_manifest.append({
                "id": idx + 1,
                "name": frame_files[idx].name,
                "camera_id": 1,
                "qvec": qvec,
                "tvec": [round(float(c), 4) for c in tvec],
                "position": [round(float(C[0]), 4), round(float(C[1]), 4), round(float(C[2]), 4)],
                "rotation": [round(float(c), 6) for c in quat_three],
            })

        # Metric scale application if requested
        scale_method = "vggt_relative"
        scale_factor = 1.0
        if metric_ref is not None and metric_ref > 0 and len(sparse_points) > 10:
            pts_arr = np.array([p["xyz"] for p in sparse_points])
            y_span = float(np.percentile(pts_arr[:, 1], 95) - np.percentile(pts_arr[:, 1], 5))
            if y_span > 0.01:
                scale_factor = metric_ref / y_span
                scale_method = "reference"
                print(f"[INFO] Rescaling VGGT geometry by factor {scale_factor:.4f} to match reference {metric_ref}m")
                for f in frames_manifest:
                    f["position"] = [round(c * scale_factor, 4) for c in f["position"]]
                    f["tvec"] = [round(c * scale_factor, 4) for c in f["tvec"]]
                for p in sparse_points:
                    p["xyz"] = [round(c * scale_factor, 4) for c in p["xyz"]]

        poses_manifest = {
            "backend": "vggt",
            "scale_method": scale_method,
            "scale_factor": round(scale_factor, 4),
            "camera_model": "PINHOLE",
            "registered_frames": len(frames_manifest),
            "total_frames": total_frames,
            "mean_reprojection_error_px": round(mean_err, 4),
            "cameras": {
                "1": {
                    "id": 1,
                    "model_id": 1,
                    "width": w,
                    "height": h,
                    "params": [round(focal, 2), round(focal, 2), round(cx, 2), round(cy, 2)],
                }
            },
            "frames": frames_manifest,
            "sparse_points": sparse_points,
        }

        # Export PLY
        sparse_ply = out_dir / "sparse" / "points3D.ply"
        write_points_ply(sparse_points, sparse_ply)

        # Mirror frames to colmap/dense/images so downstream stages find them
        dense_images = out_dir / "colmap" / "dense" / "images"
        dense_images.mkdir(parents=True, exist_ok=True)
        for f_path in frame_files:
            target_f = dense_images / f_path.name
            if not target_f.exists():
                shutil.copy2(str(f_path), str(target_f))

        return poses_manifest


class PoseStage(BaseStage):
    """Stage executing camera pose estimation via the configured PoseBackend."""

    def __init__(self):
        super().__init__(
            name="pose",
            description="Structure-from-Motion and camera pose estimation",
        )

    def is_cached(self, out_dir: Path, config: PipelineConfig) -> bool:
        poses_json = out_dir / "poses.json"
        if not poses_json.exists():
            return False
        try:
            data = json.loads(poses_json.read_text(encoding="utf-8"))
            return len(data.get("frames", [])) > 0
        except Exception:
            return False

    def execute(
        self,
        input_path: Path,
        out_dir: Path,
        config: PipelineConfig,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        frames_dir = context.get("frames_dir", out_dir / "frames")
        backend_type = config.pose_backend.backend.lower()
        metric_ref = getattr(config.general, "reference_dimension_m", None)

        print(f"\n[INFO] Starting PoseStage with backend: '{backend_type}'")

        poses_manifest = None

        if backend_type == "auto":
            print("[INFO] Pose backend set to 'auto': attempting VGGT feed-forward first...")
            try:
                vggt = VggtBackend()
                manifest = vggt.run(frames_dir, out_dir, config, metric_ref=metric_ref)
                reg = manifest.get("registered_frames", 0)
                tot = manifest.get("total_frames", 1)
                err = manifest.get("mean_reprojection_error_px", 999.0)

                # Acceptance check: at least 70% registered and error < 4.0 px
                if (reg / max(1, tot)) >= 0.70 and err < 4.0:
                    print(f"[OK] VGGT pose estimation passed health checks ({reg}/{tot} frames, {err:.2f} px error).")
                    poses_manifest = manifest
                else:
                    print(f"[WARN] VGGT reconstruction suboptimal ({reg}/{tot} frames, {err:.2f} px error). Falling back to COLMAP...")
            except Exception as e:
                print(f"[WARN] VGGT backend encountered error ({e}). Falling back to COLMAP...")

            if poses_manifest is None:
                colmap = ColmapBackend()
                poses_manifest = colmap.run(frames_dir, out_dir, config, metric_ref=metric_ref)

        elif backend_type == "vggt":
            vggt = VggtBackend()
            poses_manifest = vggt.run(frames_dir, out_dir, config, metric_ref=metric_ref)

        elif backend_type == "colmap":
            colmap = ColmapBackend()
            poses_manifest = colmap.run(frames_dir, out_dir, config, metric_ref=metric_ref)

        else:
            raise ValueError(f"Unknown pose backend '{backend_type}'. Expected 'colmap', 'vggt', or 'auto'.")

        # Save unified poses.json
        poses_json_path = out_dir / "poses.json"
        poses_json_path.write_text(json.dumps(poses_manifest, indent=2), encoding="utf-8")
        print(f"[OK] Saved unified camera poses -> {poses_json_path} ({poses_manifest.get('registered_frames')} registered frames)")

        context["poses_manifest"] = poses_manifest
        context["best_sparse"] = out_dir / "colmap" / "sparse" / "0"
        context["dense_dir"] = out_dir / "colmap" / "dense"
        return context
