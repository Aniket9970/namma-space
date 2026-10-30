#!/usr/bin/env python3
"""
build_photosphere_tour.py
─────────────────────────────────────────────────────────────────────────────
Generates a Matterport / Google Street View style Photosphere Tour from
video keyframes and COLMAP camera poses.

Outputs:
  ../backend/static/panoramas/<slug>/
    ├── tour.json           # Navigation graph (nodes, coordinates, connections)
    ├── node_0.jpg          # High-resolution panoramic view for Node 0
    ├── node_1.jpg          # High-resolution panoramic view for Node 1
    └── ...
"""

import argparse
import json
import math
import os
import shutil
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent
WORKSPACE_ROOT = ROOT.parent.parent
BACKEND_DIR = ROOT.parent / "backend"
BACKEND_STATIC = BACKEND_DIR / "static"


sys.path.append(str(ROOT.parent / "gaussian-splatting"))
from scene.colmap_loader import read_extrinsics_binary, qvec2rotmat


def compute_laplacian_variance(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return cv2.Laplacian(gray, cv2.CV_64F).var()


def build_tour(slug="60fps", num_nodes=7):
    dense_dir = ROOT / "output" / "colmap" / "dense"
    images_dir = dense_dir / "images"
    sparse_bin = dense_dir / "sparse" / "0" / "images.bin"
    if not sparse_bin.exists():
        sparse_bin = ROOT / "output" / "colmap" / "sparse" / "1" / "images.bin"
    if not sparse_bin.exists():
        sparse_bin = ROOT / "output" / "colmap" / "sparse" / "0" / "images.bin"

    if not sparse_bin.exists() or not images_dir.exists():
        print(f"[ERROR] Required COLMAP data not found in {dense_dir}")
        return False

    out_tour_dir = BACKEND_STATIC / "panoramas" / slug
    out_tour_dir.mkdir(parents=True, exist_ok=True)

    print(f"[INFO] Reading camera poses from {sparse_bin}...")
    extr = read_extrinsics_binary(str(sparse_bin))
    sorted_items = sorted(extr.items(), key=lambda x: x[1].name)

    centers = []
    names = []
    for k, im in sorted_items:
        R = qvec2rotmat(im.qvec)
        T = np.array(im.tvec)
        C = -R.T @ T
        centers.append(C)
        names.append(im.name)
    centers = np.array(centers)
    total_frames = len(centers)
    print(f"[INFO] Processed {total_frames} camera viewpoints.")

    # Normalize coordinates to Three.js world space:
    # Three.js: X=right, Y=up (eye height=1.65), Z=depth
    cx = (centers[:, 0].min() + centers[:, 0].max()) / 2.0
    cz = (centers[:, 2].min() + centers[:, 2].max()) / 2.0
    norm_x = centers[:, 0] - cx
    norm_z = centers[:, 2] - cz

    # Select node keyframe indices evenly distributed along trajectory
    node_indices = np.linspace(0, total_frames - 1, min(num_nodes, total_frames), dtype=int)

    # Standard room location names
    room_names = [
        "Entrance Foyer",
        "Living Room View A",
        "Living Room View B",
        "Dining / Hallway",
        "Kitchenette Area",
        "Bedroom Suite",
        "Balcony / Window View",
        "Interior Corner"
    ]

    nodes_data = []

    for idx, frame_idx in enumerate(node_indices):
        node_id = f"node_{idx}"
        keyframe_name = names[frame_idx]
        pos_x = float(norm_x[frame_idx])
        pos_z = float(norm_z[frame_idx])
        pos_y = 1.65  # Standard eye height above floor (Y=0)

        name = room_names[idx] if idx < len(room_names) else f"Area {idx+1}"

        # Attempt panorama stitching around frame_idx
        window_start = max(0, frame_idx - 4)
        window_end = min(total_frames, frame_idx + 5)
        window_names = names[window_start:window_end:2]

        pano_saved = False
        out_img_path = out_tour_dir / f"{node_id}.jpg"

        if len(window_names) >= 3:
            candidate_imgs = []
            for wname in window_names:
                fpath = images_dir / wname
                if fpath.exists():
                    img = cv2.imread(str(fpath))
                    if img is not None:
                        # Resize for stitching speed while preserving aspect ratio
                        h, w = img.shape[:2]
                        scale = 1280.0 / max(w, h)
                        nw, nh = int(round(w * scale)), int(round(h * scale))
                        candidate_imgs.append(cv2.resize(img, (nw, nh)))
            if len(candidate_imgs) >= 3:
                stitcher = cv2.Stitcher_create(cv2.Stitcher_PANORAMA)
                ret, pano = stitcher.stitch(candidate_imgs)
                if ret == cv2.Stitcher_OK and pano is not None:
                    # Save stitched panorama
                    cv2.imwrite(str(out_img_path), pano, [int(cv2.IMWRITE_JPEG_QUALITY), 92])
                    pano_saved = True
                    print(f"[OK] Stitched panorama for {node_id} ({name}): shape {pano.shape}")

        if not pano_saved:
            # Fallback to sharpest single frame in window
            best_img = None
            best_var = -1.0
            for wname in names[window_start:window_end]:
                fpath = images_dir / wname
                if fpath.exists():
                    img = cv2.imread(str(fpath))
                    if img is not None:
                        var = compute_laplacian_variance(img)
                        if var > best_var:
                            best_var = var
                            best_img = img
            if best_img is not None:
                cv2.imwrite(str(out_img_path), best_img, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
                print(f"[OK] Saved sharpest keyframe for {node_id} ({name}) from {keyframe_name}")

        image_url = f"/static/panoramas/{slug}/{node_id}.jpg"

        nodes_data.append({
            "id": node_id,
            "name": name,
            "position": [round(pos_x, 3), pos_y, round(pos_z, 3)],
            "image_url": image_url,
            "connections": []
        })

    # Build bidirectional navigation connections between adjacent nodes & close neighbors
    for i in range(len(nodes_data)):
        # Adjacent sequential connection
        if i > 0:
            nodes_data[i]["connections"].append(nodes_data[i-1]["id"])
        if i < len(nodes_data) - 1:
            nodes_data[i]["connections"].append(nodes_data[i+1]["id"])

        # Spatial distance connection (if within 4.0 meters)
        p_i = np.array(nodes_data[i]["position"])[[0, 2]]
        for j in range(len(nodes_data)):
            if abs(i - j) > 1:
                p_j = np.array(nodes_data[j]["position"])[[0, 2]]
                dist = np.linalg.norm(p_i - p_j)
                if dist < 3.5:
                    nodes_data[i]["connections"].append(nodes_data[j]["id"])

    tour_manifest = {
        "slug": slug,
        "default_node": "node_0",
        "nodes": nodes_data
    }

    manifest_path = out_tour_dir / "tour.json"
    with open(manifest_path, "w") as f:
        json.dump(tour_manifest, f, indent=2)

    print(f"\n[OK] Photosphere Tour generated -> {manifest_path}")
    print(f"     Total nodes: {len(nodes_data)}")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Matterport-style Photosphere Tour from video")
    parser.add_argument("--slug", default="60fps", help="Scene slug identifier")
    parser.add_argument("--nodes", type=int, default=7, help="Number of spatial nodes to generate")
    args = parser.parse_args()

    build_tour(slug=args.slug, num_nodes=args.nodes)
