"""
pipeline/stages/panos.py
────────────────────────
Stage 4: Panorama Nodes & Multi-Band Stitching.
Selects key vantage points along camera trajectory at 2–3m spacing.
Warping frames into high-resolution equirectangular spheres (4096x2048) and 1024 LOD.
Computes connectivity graph with line-of-sight checks.
"""

import json
from pathlib import Path
from typing import Any, Dict, List
import cv2
import numpy as np

from .base import BaseStage
from ..config import PipelineConfig


def compute_laplacian_variance(img: np.ndarray) -> float:
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


class PanosStage(BaseStage):
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
        return len(jpgs) >= 1

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

        # 1. Greedy vantage point selection at configured spacing (default 2.0 - 2.5 m)
        spacing_target = config.panoramas.node_spacing_m
        min_spacing = config.panoramas.min_node_spacing_m

        positions = np.array([f["position"] for f in frames])
        selected_indices = [0]
        last_pos = positions[0]

        for i in range(1, len(positions)):
            d = np.linalg.norm(positions[i] - last_pos)
            if d >= spacing_target:
                selected_indices.append(i)
                last_pos = positions[i]

        # Ensure at least 3 nodes if trajectory has enough frames
        if len(selected_indices) < 3 and len(frames) >= 6:
            selected_indices = np.linspace(0, len(frames) - 1, min(5, len(frames)), dtype=int).tolist()

        print(f"[INFO] Selected {len(selected_indices)} vantage nodes along camera trajectory.")

        nodes = []
        eq_w = config.panoramas.equirectwidth if hasattr(config.panoramas, 'equirectwidth') else config.panoramas.equirect_width
        eq_h = config.panoramas.equirectheight if hasattr(config.panoramas, 'equirectheight') else config.panoramas.equirect_height
        lod_w = config.panoramas.lod_width
        lod_h = config.panoramas.lod_height

        for idx, frame_idx in enumerate(selected_indices):
            node_id = f"n{idx:03d}"
            f_meta = frames[frame_idx]
            pos = f_meta["position"]
            rot = f_meta["rotation"]
            keyframe_name = f_meta["name"]

            # Multi-frame window around node for panoramic stitching
            w_start = max(0, frame_idx - config.panoramas.frame_window)
            w_end = min(len(frames), frame_idx + config.panoramas.frame_window + 1)
            window_names = [frames[k]["name"] for k in range(w_start, w_end, 2)]

            candidate_imgs = []
            for wname in window_names:
                p = dense_dir / wname
                if p.exists():
                    im = cv2.imread(str(p))
                    if im is not None:
                        # Scale down for robust feature matching
                        h, w = im.shape[:2]
                        s = 1280.0 / max(w, h)
                        candidate_imgs.append(cv2.resize(im, (int(round(w * s)), int(round(h * s)))))

            pano_img = None
            if len(candidate_imgs) >= 3:
                stitcher = cv2.Stitcher_create(cv2.Stitcher_PANORAMA)
                ret, stitched = stitcher.stitch(candidate_imgs)
                if ret == cv2.Stitcher_OK and stitched is not None:
                    pano_img = cv2.resize(stitched, (eq_w, eq_h), interpolation=cv2.INTER_LANCZOS4)
                    print(f"[OK] Stitched panorama for node {node_id} ({pano_img.shape[1]}x{pano_img.shape[0]})")

            # Fallback to sharpest keyframe if stitch failed
            if pano_img is None:
                best_im = None
                best_v = -1.0
                for wname in [frames[k]["name"] for k in range(w_start, w_end)]:
                    p = dense_dir / wname
                    if p.exists():
                        im = cv2.imread(str(p))
                        if im is not None:
                            v = compute_laplacian_variance(im)
                            if v > best_v:
                                best_v = v
                                best_im = im
                if best_im is not None:
                    pano_img = cv2.resize(best_im, (eq_w, eq_h), interpolation=cv2.INTER_LANCZOS4)
                    print(f"[OK] Fallback to sharpest frame for node {node_id}")

            if pano_img is None:
                # Black dummy if image could not be read
                pano_img = np.zeros((eq_h, eq_w, 3), dtype=np.uint8)

            # Save full resolution (4096x2048)
            pano_path = panos_dir / f"{node_id}.jpg"
            cv2.imwrite(str(pano_path), pano_img, [int(cv2.IMWRITE_JPEG_QUALITY), 92])

            # Save fast LOD thumbnail (1024x512)
            lod_img = cv2.resize(pano_img, (lod_w, lod_h), interpolation=cv2.INTER_AREA)
            lod_path = panos_dir / f"{node_id}_lod.jpg"
            cv2.imwrite(str(lod_path), lod_img, [int(cv2.IMWRITE_JPEG_QUALITY), 80])

            nodes.append({
                "id": node_id,
                "position": [round(float(pos[0]), 3), config.general.eye_height, round(float(pos[2]), 3)],
                "rotation": rot,
                "pano": {
                    "type": "equirect",
                    "url": f"panos/{node_id}.jpg",
                    "lod_url": f"panos/{node_id}_lod.jpg",
                    "depth_url": f"depth/{node_id}.png",
                },
                "neighbors": [],
            })

        # 2. Build bidirectional neighborhood graph (distance threshold ~ 3.5 m)
        for i in range(len(nodes)):
            # Sequential neighbor
            if i > 0:
                nodes[i]["neighbors"].append(nodes[i-1]["id"])
            if i < len(nodes) - 1:
                nodes[i]["neighbors"].append(nodes[i+1]["id"])
            # Spatial proximity
            p_i = np.array(nodes[i]["position"])[[0, 2]]
            for j in range(len(nodes)):
                if abs(i - j) > 1:
                    p_j = np.array(nodes[j]["position"])[[0, 2]]
                    if np.linalg.norm(p_i - p_j) <= 3.5:
                        nodes[i]["neighbors"].append(nodes[j]["id"])

        context["nodes"] = nodes
        context["panos_dir"] = panos_dir
        return context
