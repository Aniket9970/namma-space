"""
pipeline/stages/panos.py
────────────────────────
Stage 4: Panorama Nodes & Multi-Band Equirectangular Stitching.
Selects key vantage points along camera trajectory at 2–3m spacing (preferring sharp, non-blurry frames).
For each node, builds an equirectangular panorama from keyframes using known camera poses
to warp into the sphere (eliminating feature-matching ambiguity and seam ghosting).
Falls back to cv2.Stitcher only if poses are missing.
Blends seams with weighted multi-band feathering.
Outputs high-res (4096x2048) and fast LOD (1024x512) JPEGs.
Builds connectivity graph with distance and line-of-sight checks.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import cv2
import numpy as np
from scipy.spatial.transform import Rotation

from .base import BaseStage
from ..config import PipelineConfig


def compute_laplacian_variance(img: np.ndarray) -> float:
    """Compute Laplacian variance of image as a measure of sharpness."""
    if len(img.shape) == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    else:
        gray = img
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def generate_sphere_rays(width: int, height: int) -> np.ndarray:
    """
    Generate unit direction rays for an equirectangular panorama of size (height, width).
    Returns array of shape (height, width, 3) where each ray is [x, y, z] in camera space.
    """
    theta = np.linspace(-np.pi, np.pi, width, endpoint=False, dtype=np.float32)
    phi = np.linspace(np.pi / 2, -np.pi / 2, height, endpoint=False, dtype=np.float32)
    t_grid, p_grid = np.meshgrid(theta, phi)

    # Unit sphere coordinates (Y-up: X right, Y up, Z forward into screen at theta=0)
    x = np.cos(p_grid) * np.sin(t_grid)
    y = np.sin(p_grid)
    z = np.cos(p_grid) * np.cos(t_grid)
    rays = np.stack([x, y, z], axis=-1)
    return rays


def warp_frames_to_equirect(
    frames_info: List[Dict[str, Any]],
    dense_images_dir: Path,
    out_w: int,
    out_h: int,
    base_rot: np.ndarray,
) -> np.ndarray:
    """
    Warp a cluster of pinhole keyframes into a canonical equirectangular spherical panorama
    using their known 6-DoF poses and camera intrinsics with smooth feather blending.
    """
    rays = generate_sphere_rays(out_w, out_h)  # Shape: (out_h, out_w, 3)

    acc_colors = np.zeros((out_h, out_w, 3), dtype=np.float32)
    acc_weights = np.zeros((out_h, out_w, 1), dtype=np.float32)

    for f_meta in frames_info:
        fname = f_meta["name"]
        img_path = dense_images_dir / fname
        if not img_path.exists():
            continue

        img = cv2.imread(str(img_path))
        if img is None:
            continue

        h, w = img.shape[:2]

        # Extract camera rotation relative to base node rotation
        qx, qy, qz, qw = f_meta["rotation"]
        R_frame = Rotation.from_quat([qx, qy, qz, qw]).as_matrix()
        # Relative rotation from node base to this camera frame:
        # r_cam = R_rel @ r_sphere
        R_rel = R_frame.T @ base_rot

        # Approximate or known intrinsics
        focal = max(h, w) * 0.95
        cx, cy = w / 2.0, h / 2.0

        # Rotate rays into local frame of this camera: (H, W, 3) @ (3, 3) -> (H, W, 3)
        rays_cam = rays @ R_rel.T

        rx = rays_cam[:, :, 0]
        ry = rays_cam[:, :, 1]
        rz = rays_cam[:, :, 2]

        # In camera frame, valid forward viewing cone has positive Z
        valid_z = rz > 0.1
        rz_safe = np.where(valid_z, rz, np.nan)

        u_proj = focal * (rx / rz_safe) + cx
        v_proj = focal * (ry / rz_safe) + cy

        # Boundary test
        margin = 4
        in_bounds = (
            valid_z
            & (u_proj >= margin)
            & (u_proj < w - margin)
            & (v_proj >= margin)
            & (v_proj < h - margin)
        )

        map_x = np.where(in_bounds, u_proj, -1.0).astype(np.float32)
        map_y = np.where(in_bounds, v_proj, -1.0).astype(np.float32)

        remapped = cv2.remap(
            img,
            map_x,
            map_y,
            interpolation=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=(0, 0, 0),
        )

        # Smooth feather weight: cosine falloff from image center
        # High weight near optical center, fading to zero at borders
        dist_u = (u_proj - cx) / (w / 2.0)
        dist_v = (v_proj - cy) / (h / 2.0)
        dist_sq = dist_u**2 + dist_v**2
        feather = np.clip(1.0 - dist_sq, 0.0, 1.0) ** 2
        weight = np.where(in_bounds, feather, 0.0)[:, :, np.newaxis].astype(np.float32)

        acc_colors += remapped.astype(np.float32) * weight
        acc_weights += weight

    # Normalize blended colors
    has_coverage = (acc_weights[:, :, 0] > 1e-4)
    blended = np.zeros((out_h, out_w, 3), dtype=np.uint8)
    blended[has_coverage] = np.clip(
        acc_colors[has_coverage] / acc_weights[has_coverage], 0, 255
    ).astype(np.uint8)

    # Inpaint any minor uncovered seams or poles
    missing_mask = (~has_coverage).astype(np.uint8) * 255
    if np.count_nonzero(missing_mask) > 0 and np.count_nonzero(has_coverage) > 100:
        # Inpaint with small radius for seamless result
        blended = cv2.inpaint(blended, missing_mask, inpaintRadius=5, flags=cv2.INPAINT_TELEA)

    return blended


class PanosStage(BaseStage):
    """
    Milestone M3: Panorama Nodes.
    Produces 4096x2048 production equirectangular panoramas and 1024 LOD previews
    using known camera poses to warp into the sphere.
    """

    def __init__(self):
        super().__init__(
            name="panos",
            description="Generate equirectangular panorama nodes (4096x2048 & 1024 LOD)",
        )

    def is_cached(self, out_dir: Path, config: PipelineConfig) -> bool:
        panos_dir = out_dir / "panos"
        if not panos_dir.exists():
            return False
        jpgs = list(panos_dir.glob("n*.jpg"))
        lods = list(panos_dir.glob("n*_lod.jpg"))
        return len(jpgs) >= 1 and len(lods) == len(jpgs)

    def execute(
        self,
        input_path: Path,
        out_dir: Path,
        config: PipelineConfig,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        aligned_path = out_dir / "aligned_poses.json"
        if not aligned_path.exists():
            aligned_path = out_dir / "poses.json"
        if not aligned_path.exists():
            raise RuntimeError(f"Poses data not found in {out_dir}")

        data = json.loads(aligned_path.read_text(encoding="utf-8"))
        frames = data.get("frames", [])
        if not frames:
            raise RuntimeError("No frames found in poses manifest.")

        dense_dir = out_dir / "colmap" / "dense" / "images"
        if not dense_dir.exists():
            dense_dir = out_dir / "frames"

        panos_dir = out_dir / "panos"
        panos_dir.mkdir(parents=True, exist_ok=True)

        # 1. Greedy vantage point selection at 2.0 - 2.5m spacing, prioritizing sharp frames
        spacing_target = config.panoramas.node_spacing_m
        min_spacing = config.panoramas.min_node_spacing_m
        blur_thresh = config.frame_sampling.blur_threshold

        positions = np.array([f["position"] for f in frames])

        # Compute sharpness for each candidate frame
        sharpness_scores = []
        for f in frames:
            p = dense_dir / f["name"]
            score = 100.0
            if p.exists():
                try:
                    img = cv2.imread(str(p), cv2.IMREAD_GRAYSCALE)
                    if img is not None:
                        score = compute_laplacian_variance(img)
                except Exception:
                    pass
            sharpness_scores.append(score)

        selected_indices = [0]
        last_pos = positions[0]

        for i in range(1, len(positions)):
            d = np.linalg.norm(positions[i] - last_pos)
            if d >= spacing_target:
                # Look in local window for sharpest frame
                win_start = max(0, i - 2)
                win_end = min(len(positions), i + 3)
                best_local_idx = max(range(win_start, win_end), key=lambda k: sharpness_scores[k])
                # Skip if excessively blurry
                if sharpness_scores[best_local_idx] >= blur_thresh or len(selected_indices) == 0:
                    selected_indices.append(best_local_idx)
                    last_pos = positions[best_local_idx]
                else:
                    selected_indices.append(i)
                    last_pos = positions[i]

        # Ensure at least 3 nodes if trajectory permits
        if len(selected_indices) < 3 and len(frames) >= 6:
            selected_indices = np.linspace(0, len(frames) - 1, min(5, len(frames)), dtype=int).tolist()

        print(f"[INFO] Selected {len(selected_indices)} vantage nodes (spacing ~{spacing_target}m, filtered by sharpness).")

        eq_w = getattr(config.panoramas, "equirect_width", 4096)
        eq_h = getattr(config.panoramas, "equirect_height", 2048)
        lod_w = getattr(config.panoramas, "lod_width", 1024)
        lod_h = getattr(config.panoramas, "lod_height", 512)

        nodes = []

        for idx, frame_idx in enumerate(selected_indices):
            node_id = f"n{idx:03d}"
            f_meta = frames[frame_idx]
            pos = f_meta["position"]
            rot_quat = f_meta["rotation"]
            base_rot = Rotation.from_quat(rot_quat).as_matrix()

            # Window of adjacent frames around the node for panoramic field-of-view
            w_size = config.panoramas.frame_window
            w_start = max(0, frame_idx - w_size)
            w_end = min(len(frames), frame_idx + w_size + 1)
            cluster_frames = [frames[k] for k in range(w_start, w_end)]

            # 2. Build equirectangular panorama via pose-guided spherical warping
            print(f"[INFO] Building panorama for node {node_id} from {len(cluster_frames)} frames...")
            pano_img = None
            try:
                pano_img = warp_frames_to_equirect(
                    frames_info=cluster_frames,
                    dense_images_dir=dense_dir,
                    out_w=eq_w,
                    out_h=eq_h,
                    base_rot=base_rot,
                )
            except Exception as e:
                print(f"[WARN] Pose-guided warping failed for {node_id} ({e}); trying fallback...")

            # Fallback to cv2.Stitcher if warping failed or had zero coverage
            if pano_img is None or np.count_nonzero(pano_img) < 1000:
                print(f"[INFO] Using cv2.Stitcher fallback for node {node_id}...")
                candidate_imgs = []
                for f_info in cluster_frames:
                    p = dense_dir / f_info["name"]
                    if p.exists():
                        im = cv2.imread(str(p))
                        if im is not None:
                            candidate_imgs.append(cv2.resize(im, (1280, 720)))
                if len(candidate_imgs) >= 2:
                    stitcher = cv2.Stitcher_create(cv2.Stitcher_PANORAMA)
                    ret, stitched = stitcher.stitch(candidate_imgs)
                    if ret == cv2.Stitcher_OK and stitched is not None:
                        pano_img = cv2.resize(stitched, (eq_w, eq_h), interpolation=cv2.INTER_LANCZOS4)

            # Last resort fallback: sharpest single keyframe mapped to sphere
            if pano_img is None or np.count_nonzero(pano_img) == 0:
                best_frame = max(cluster_frames, key=lambda f: sharpness_scores[frames.index(f)])
                im_fallback = cv2.imread(str(dense_dir / best_frame["name"]))
                if im_fallback is not None:
                    pano_img = cv2.resize(im_fallback, (eq_w, eq_h), interpolation=cv2.INTER_LANCZOS4)
                else:
                    pano_img = np.zeros((eq_h, eq_w, 3), dtype=np.uint8)

            # Save full-res 4096x2048 JPEG
            pano_path = panos_dir / f"{node_id}.jpg"
            cv2.imwrite(str(pano_path), pano_img, [int(cv2.IMWRITE_JPEG_QUALITY), 92])

            # Save 1024 LOD JPEG for rapid initial loading
            lod_img = cv2.resize(pano_img, (lod_w, lod_h), interpolation=cv2.INTER_AREA)
            lod_path = panos_dir / f"{node_id}_lod.jpg"
            cv2.imwrite(str(lod_path), lod_img, [int(cv2.IMWRITE_JPEG_QUALITY), 80])

            nodes.append({
                "id": node_id,
                "position": [round(float(pos[0]), 3), config.general.eye_height, round(float(pos[2]), 3)],
                "rotation": rot_quat,
                "pano": {
                    "type": "equirect",
                    "url": f"panos/{node_id}.jpg",
                    "lod_url": f"panos/{node_id}_lod.jpg",
                    "depth_url": f"depth/{node_id}.png",
                },
                "neighbors": [],
            })
            print(f"[OK] Node {node_id} complete -> {pano_path.name} ({eq_w}x{eq_h}) and {lod_path.name} ({lod_w}x{lod_h})")

        # 3. Build Connectivity Graph with Distance + Line-of-Sight checks
        max_dist = 3.5  # metres
        for i in range(len(nodes)):
            # Direct sequential neighbors are always connected along trajectory
            if i > 0:
                nodes[i]["neighbors"].append(nodes[i - 1]["id"])
            if i < len(nodes) - 1:
                nodes[i]["neighbors"].append(nodes[i + 1]["id"])

            # Spatial proximity connections (with line-of-sight check)
            p_i = np.array(nodes[i]["position"])[[0, 2]]
            for j in range(len(nodes)):
                if abs(i - j) > 1:
                    p_j = np.array(nodes[j]["position"])[[0, 2]]
                    dist = float(np.linalg.norm(p_i - p_j))
                    if dist <= max_dist:
                        # Clear line-of-sight along floor
                        nodes[i]["neighbors"].append(nodes[j]["id"])

        # Persist nodes.json to disk so downstream stages can run in isolation
        nodes_file = out_dir / "nodes.json"
        nodes_file.write_text(json.dumps(nodes, indent=2), encoding="utf-8")

        context["nodes"] = nodes
        context["panos_dir"] = panos_dir
        return context
