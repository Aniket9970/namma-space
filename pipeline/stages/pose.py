"""
pipeline/stages/pose.py
───────────────────────
Stage 2: Camera Pose Estimation & Structure-from-Motion.
Implements the PoseBackend interface (COLMAP and extensible for VGGT in M1).
Outputs a unified poses.json and standard COLMAP sparse/dense directory.
"""

from abc import ABC, abstractmethod
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
from typing import Any, Dict, List
import numpy as np

from .base import BaseStage
from ..config import PipelineConfig

# Ensure COLMAP bin is on PATH
for candidate in [
    Path(os.environ.get("USERPROFILE", "")) / "colmap" / "bin",
    Path("C:/colmap/bin"),
    Path("C:/colmap"),
    Path(__file__).resolve().parent.parent.parent / "colmap" / "bin",
]:
    if candidate.exists() and str(candidate) not in os.environ.get("PATH", ""):
        os.environ["PATH"] = str(candidate) + os.pathsep + os.environ.get("PATH", "")


def qvec2rotmat(qvec: List[float] | np.ndarray) -> np.ndarray:
    w, x, y, z = qvec
    return np.array([
        [1 - 2*y*y - 2*z*z, 2*x*y - 2*z*w,     2*x*z + 2*y*w],
        [2*x*y + 2*z*w,     1 - 2*x*x - 2*z*z, 2*y*z - 2*x*w],
        [2*x*z - 2*y*w,     2*y*z + 2*x*w,     1 - 2*x*x - 2*y*y]
    ])


def read_images_bin(path: Path) -> Dict[int, Any]:
    """Read COLMAP images.bin without external dependencies."""
    images = {}
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
            f.seek(num_points2D * 24, 1)  # Skip 2D points (x, y, id)
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
    with open(path, "rb") as f:
        num_cameras = struct.unpack("<Q", f.read(8))[0]
        for _ in range(num_cameras):
            cam_id = struct.unpack("<I", f.read(4))[0]
            model_id = struct.unpack("<i", f.read(4))[0]
            width = struct.unpack("<Q", f.read(8))[0]
            height = struct.unpack("<Q", f.read(8))[0]
            # SIMPLE_RADIAL has 4 params (f, cx, cy, k)
            # PINHOLE has 4 params (fx, fy, cx, cy)
            num_params = 4
            params = struct.unpack(f"<{num_params}d", f.read(num_params * 8))
            cameras[cam_id] = {
                "id": cam_id,
                "model_id": model_id,
                "width": width,
                "height": height,
                "params": list(params),
            }
    return cameras


class PoseBackend(ABC):
    @abstractmethod
    def run(self, frames_dir: Path, out_colmap_dir: Path, config: PipelineConfig) -> Path:
        """Run camera pose estimation and return path to best sparse model folder."""
        pass


class ColmapBackend(PoseBackend):
    def run(self, frames_dir: Path, out_colmap_dir: Path, config: PipelineConfig) -> Path:
        colmap_exe = shutil.which("colmap")
        if not colmap_exe:
            raise RuntimeError("COLMAP executable not found on system PATH.")

        db_path = out_colmap_dir / "database.db"
        sparse_dir = out_colmap_dir / "sparse"
        dense_dir = out_colmap_dir / "dense"
        out_colmap_dir.mkdir(parents=True, exist_ok=True)
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

        # Select best sparse model by points3D.bin size
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

        # Ensure dense/sparse/0 has the binary files
        dense_sparse_0 = dense_dir / "sparse" / "0"
        dense_sparse_0.mkdir(parents=True, exist_ok=True)
        for f in (dense_dir / "sparse").glob("*.bin"):
            shutil.copy2(str(f), str(dense_sparse_0 / f.name))

        return best_model


class PoseStage(BaseStage):
    def __init__(self):
        super().__init__(
            name="pose",
            description="Structure-from-Motion and camera pose estimation",
        )

    def is_cached(self, out_dir: Path, config: PipelineConfig) -> bool:
        poses_json = out_dir / "poses.json"
        dense_images = out_dir / "colmap" / "dense" / "images"
        return poses_json.exists() and dense_images.exists() and len(list(dense_images.glob("*.*"))) > 0

    def execute(
        self,
        input_path: Path,
        out_dir: Path,
        config: PipelineConfig,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        frames_dir = context.get("frames_dir", out_dir / "frames")
        colmap_dir = out_dir / "colmap"

        backend_type = config.pose_backend.backend.lower()
        if backend_type in ["auto", "colmap"]:
            backend = ColmapBackend()
        else:
            print(f"[WARN] Pose backend '{backend_type}' falling back to COLMAP in baseline.")
            backend = ColmapBackend()

        best_sparse = backend.run(frames_dir, colmap_dir, config)

        # Generate unified poses.json
        images_bin = best_sparse / "images.bin"
        cameras_bin = best_sparse / "cameras.bin"
        if not images_bin.exists():
            dense_images_bin = colmap_dir / "dense" / "sparse" / "0" / "images.bin"
            if dense_images_bin.exists():
                images_bin = dense_images_bin

        raw_images = read_images_bin(images_bin) if images_bin.exists() else {}
        raw_cameras = read_cameras_bin(cameras_bin) if cameras_bin.exists() else {}

        frames_manifest = []
        for img_id, img_info in sorted(raw_images.items(), key=lambda x: x[1]["name"]):
            qvec = img_info["qvec"]
            tvec = img_info["tvec"]
            R = qvec2rotmat(qvec)
            C = -R.T @ np.array(tvec)  # Camera center in world space
            # Quaternion format: Three.js uses [x, y, z, w]
            qw, qx, qy, qz = qvec
            frames_manifest.append({
                "id": img_id,
                "name": img_info["name"],
                "qvec": qvec,
                "tvec": tvec,
                "position": [round(float(C[0]), 4), round(float(C[1]), 4), round(float(C[2]), 4)],
                "rotation": [round(float(qx), 6), round(float(qy), 6), round(float(qz), 6), round(float(qw), 6)],
            })

        poses_manifest = {
            "backend": "colmap",
            "camera_model": config.pose_backend.colmap.camera_model,
            "registered_frames": len(frames_manifest),
            "cameras": raw_cameras,
            "frames": frames_manifest,
        }

        poses_json_path = out_dir / "poses.json"
        poses_json_path.write_text(json.dumps(poses_manifest, indent=2), encoding="utf-8")
        print(f"[OK] Saved unified camera poses -> {poses_json_path} ({len(frames_manifest)} registered frames)")

        context["best_sparse"] = best_sparse
        context["poses_manifest"] = poses_manifest
        context["dense_dir"] = colmap_dir / "dense"
        return context
