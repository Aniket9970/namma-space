#!/usr/bin/env python3
"""
export_web.py
─────────────────────────────────────────────────────────────────────────────
Convert Nerfstudio Poisson mesh (.ply) to .glb and copy web-ready assets to
the backend static directory.

Outputs:
  ../backend/static/models/scene.glb   — mesh for Three.js GLB loader
  ../backend/static/models/scene.splat — 3DGS splat for gsplat viewer

Usage:
    python export_web.py [--ply output/mesh/mesh.ply]
                         [--splat output/splat]
                         [--backend ../backend]
"""

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

import numpy as np

try:
    import open3d as o3d
    HAS_OPEN3D = True
except ImportError:
    o3d = None
    HAS_OPEN3D = False

try:
    import trimesh
except ImportError:
    print("[ERROR] trimesh not installed. Run: pip install trimesh", file=sys.stderr)
    sys.exit(1)


def find_best_splat(splat_dir: Path) -> Path | None:
    """Find the .splat file with the highest iteration count."""
    candidates = list(splat_dir.rglob("*.splat"))
    if not candidates:
        # Try .ply inside point_cloud directories (3DGS format)
        candidates = list(splat_dir.rglob("point_cloud.ply"))
    if not candidates:
        return None
    # Sort by iteration number embedded in path
    def sort_key(p: Path) -> int:
        for part in p.parts:
            if "iteration_" in part:
                try:
                    return int(part.split("iteration_")[-1])
                except ValueError:
                    pass
        return 0
    return sorted(candidates, key=sort_key)[-1]


def ply_to_glb(ply_path: Path, glb_path: Path) -> None:
    """Convert a PLY mesh to GLB using Open3D or trimesh."""
    print(f"[INFO] Loading PLY: {ply_path}")
    if HAS_OPEN3D and o3d is not None:
        mesh_o3d = o3d.io.read_triangle_mesh(str(ply_path))
        if len(mesh_o3d.triangles) == 0:
            print("[WARN] Open3D mesh has no triangles. Attempting trimesh fallback...")
            mesh_tm = trimesh.load(str(ply_path))
        else:
            vertices = np.asarray(mesh_o3d.vertices)
            faces = np.asarray(mesh_o3d.triangles)
            vertex_colors = None
            if mesh_o3d.has_vertex_colors():
                vertex_colors = (np.asarray(mesh_o3d.vertex_colors) * 255).astype(np.uint8)
            mesh_tm = trimesh.Trimesh(
                vertices=vertices,
                faces=faces,
                vertex_colors=vertex_colors,
                process=False,
            )
    else:
        loaded = trimesh.load(str(ply_path))
        if isinstance(loaded, trimesh.Scene):
            meshes = [g for g in loaded.geometry.values() if isinstance(g, trimesh.Trimesh)]
            mesh_tm = trimesh.util.concatenate(meshes) if meshes else None
        else:
            mesh_tm = loaded

    if mesh_tm is None:
        print("[ERROR] Failed to load mesh from PLY")
        return

    # Compute normals if missing
    mesh_tm.fix_normals()

    glb_path.parent.mkdir(parents=True, exist_ok=True)
    mesh_tm.export(str(glb_path))
    size_mb = glb_path.stat().st_size / (1024 * 1024)
    print(f"[OK] GLB exported -> {glb_path}  ({size_mb:.1f} MB)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Export web assets from reconstruction output.")
    parser.add_argument("--ply", default="output/mesh/mesh.ply", help="Input Poisson mesh PLY path")
    parser.add_argument("--splat", default="output/splat", help="3DGS output directory")
    parser.add_argument("--backend", default="../backend", help="Path to backend directory")
    parser.add_argument("--name", default="scene", help="Base filename for exported assets")
    args = parser.parse_args()

    ply_path = Path(args.ply)
    splat_dir = Path(args.splat)
    backend_models = Path(args.backend) / "static" / "models"
    backend_models.mkdir(parents=True, exist_ok=True)

    # ── Export GLB ────────────────────────────────────────────────────────────
    glb_dest = backend_models / f"{args.name}.glb"
    if ply_path.exists():
        ply_to_glb(ply_path, glb_dest)
        if args.name != "scene":
            shutil.copy2(str(glb_dest), str(backend_models / "scene.glb"))
    else:
        print(f"[WARN] PLY not found at {ply_path}. Skipping GLB export.")

    # ── Copy Splat ────────────────────────────────────────────────────────────
    splat_src = find_best_splat(splat_dir)
    splat_dest = backend_models / f"{args.name}.splat"
    if splat_src:
        if splat_src.suffix.lower() == ".ply":
            from run_pipeline import convert_ply_to_splat
            convert_ply_to_splat(splat_src, splat_dest)
        else:
            shutil.copy2(str(splat_src), str(splat_dest))
        if args.name != "scene":
            shutil.copy2(str(splat_dest), str(backend_models / "scene.splat"))
        size_mb = splat_dest.stat().st_size / (1024 * 1024)
        print(f"[OK] Splat copied -> {splat_dest}  ({size_mb:.1f} MB)")
        print(f"     Source: {splat_src}")
    else:
        print(f"[WARN] No .splat file found in {splat_dir}. Skipping.")

    print("\n[DONE] Web assets exported to backend/static/models/")
    print("       Next: python build_occupancy_grid.py")


if __name__ == "__main__":
    main()
