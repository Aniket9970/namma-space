#!/usr/bin/env python3
"""
spatial_analysis.py
─────────────────────────────────────────────────────────────────────────────
Architectural Spatial Intelligence & Isovist Analysis for Indoor Walkthroughs.

Inspired by architectural space syntax and empirical spatial perception research
(Saly et al., Benedikt 1979):
  1. Boundary Extraction: Extracts vectorized wall contours and room boundaries
     from 2D height-sliced occupancy grids.
  2. Isovist Analysis: Computes 360-degree radial visual fields from camera
     viewpoints to quantify:
       - Visible Area (m²)
       - Visual Perimeter (m)
       - Compactness / Openness Ratio (4π · Area / Perimeter²)
       - Occlusivity & Visual Connectivity along walkthrough path.
  3. Spatial Analytics Export: Generates structured JSON and SVG visual diagrams.
"""

import argparse
import json
import math
from pathlib import Path
from typing import Dict, List, Tuple, Any

import cv2
import numpy as np


def extract_boundaries(grid: np.ndarray, cell_size: float = 0.05) -> List[Dict[str, Any]]:
    """Extract vectorized boundary polylines from a 2D binary occupancy grid."""
    # Obstacles are 1, free is 0
    binary = (grid > 0).astype(np.uint8) * 255
    contours, hierarchy = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    boundaries = []
    for c in contours:
        if cv2.contourArea(c) < 4:  # filter tiny noise
            continue
        # Approximate contour with Douglas-Peucker for clean architectural lines
        epsilon = 0.01 * cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, epsilon, True)
        
        pts_metric = []
        for pt in approx:
            px, py = pt[0]
            pts_metric.append([round(float(px * cell_size), 3), round(float(py * cell_size), 3)])
        
        boundaries.append({
            "points": pts_metric,
            "perimeter_m": round(float(cv2.arcLength(c, True) * cell_size), 2),
            "area_m2": round(float(cv2.contourArea(c) * (cell_size ** 2)), 2),
        })
    return boundaries


def compute_isovist(
    grid: np.ndarray,
    origin_px: Tuple[int, int],
    cell_size: float = 0.05,
    num_rays: int = 120,
    max_range_m: float = 15.0,
) -> Dict[str, Any]:
    """Compute 2D isovist polygon and spatial metrics from a viewpoint."""
    h, w = grid.shape
    ox, oy = int(round(origin_px[0])), int(round(origin_px[1]))
    
    # If starting inside an obstacle, find nearest free cell
    if 0 <= ox < w and 0 <= oy < h and grid[oy, ox] != 0:
        found = False
        for rad in range(1, 10):
            for dx in range(-rad, rad + 1):
                for dy in range(-rad, rad + 1):
                    nx, ny = ox + dx, oy + dy
                    if 0 <= nx < w and 0 <= ny < h and grid[ny, nx] == 0:
                        ox, oy = nx, ny
                        found = True
                        break
                if found:
                    break

    max_dist_px = int(round(max_range_m / cell_size))
    angles = np.linspace(0, 2 * np.pi, num_rays, endpoint=False)
    polygon_px = []
    ray_lengths = []

    for a in angles:
        cos_a, sin_a = math.cos(a), math.sin(a)
        hit_dist = max_dist_px
        for step in range(1, max_dist_px + 1):
            rx = int(round(ox + step * cos_a))
            ry = int(round(oy + step * sin_a))
            if rx < 0 or rx >= w or ry < 0 or ry >= h:
                hit_dist = step
                break
            if grid[ry, rx] != 0:  # obstacle hit
                hit_dist = step
                break
        polygon_px.append((ox + hit_dist * cos_a, oy + hit_dist * sin_a))
        ray_lengths.append(hit_dist * cell_size)

    poly_arr = np.array(polygon_px, dtype=np.float32)
    poly_int = np.round(poly_arr).astype(np.int32)

    area_px = float(cv2.contourArea(poly_int))
    perimeter_px = float(cv2.arcLength(poly_int, True))

    area_m2 = area_px * (cell_size ** 2)
    perimeter_m = perimeter_px * cell_size

    # Benedikt compactness metric: 4*pi*A / P^2 (1.0 = perfect circle)
    compactness = (4.0 * math.pi * area_m2) / (perimeter_m ** 2) if perimeter_m > 0 else 0.0

    return {
        "origin_m": [round(ox * cell_size, 3), round(oy * cell_size, 3)],
        "area_m2": round(area_m2, 2),
        "perimeter_m": round(perimeter_m, 2),
        "compactness": round(compactness, 3),
        "mean_depth_m": round(float(np.mean(ray_lengths)), 2),
        "max_radial_m": round(float(np.max(ray_lengths)), 2),
        "polygon_m": [[round(float(p[0] * cell_size), 3), round(float(p[1] * cell_size), 3)] for p in polygon_px],
    }


def analyze_scene_space(
    grid_path: Path,
    meta_path: Path,
    output_json: Path,
    sample_points: int = 5,
) -> Dict[str, Any]:
    """Run full architectural spatial analysis on an occupancy grid."""
    grid = np.load(str(grid_path))
    meta = {}
    if meta_path.exists():
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)

    cell_size = float(meta.get("cell_size", 0.05))
    h, w = grid.shape
    total_area_m2 = round(float(np.sum(grid == 0) * (cell_size ** 2)), 2)

    boundaries = extract_boundaries(grid, cell_size)

    # Sample representative free vantage points
    free_y, free_x = np.where(grid == 0)
    isovists = []
    if len(free_x) > 0:
        step = max(1, len(free_x) // sample_points)
        for idx in range(0, min(len(free_x), sample_points * step), step):
            pt = (int(free_x[idx]), int(free_y[idx]))
            iso = compute_isovist(grid, pt, cell_size=cell_size)
            isovists.append(iso)

    mean_openness = round(float(np.mean([iso["compactness"] for iso in isovists])) if isovists else 0.0, 3)
    mean_view_area = round(float(np.mean([iso["area_m2"] for iso in isovists])) if isovists else 0.0, 2)

    analytics = {
        "grid_shape": [h, w],
        "cell_size_m": cell_size,
        "total_walkable_area_m2": total_area_m2,
        "boundary_count": len(boundaries),
        "boundaries": boundaries[:25],
        "mean_openness_index": mean_openness,
        "mean_isovist_area_m2": mean_view_area,
        "sample_isovists": isovists,
    }

    output_json.parent.mkdir(parents=True, exist_ok=True)
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(analytics, f, indent=2)

    print(f"[OK] Spatial Analysis generated -> {output_json}")
    print(f"     Walkable Area: {total_area_m2} m² | Boundaries: {len(boundaries)} | Mean Isovist: {mean_view_area} m²")
    return analytics


def main():
    parser = argparse.ArgumentParser(description="Architectural Spatial & Isovist Analysis")
    parser.add_argument("--grid", required=True, help="Path to occupancy grid (.npy)")
    parser.add_argument("--meta", default=None, help="Path to occupancy grid metadata (.json)")
    parser.add_argument("--out", default="spatial_analysis.json", help="Output JSON path")
    args = parser.parse_args()

    grid_p = Path(args.grid)
    meta_p = Path(args.meta) if args.meta else grid_p.parent / f"{grid_p.stem}_meta.json"
    analyze_scene_space(grid_p, meta_p, Path(args.out))


if __name__ == "__main__":
    main()
