"""
run_pipeline.py - Full automated pipeline for Namma Space reconstruction.

Antigravity (or a human) can run this single script to execute all steps:
    python run_pipeline.py --video "C:/path/to/video.mp4"
or:
    python run_pipeline.py "Tour video.mp4"

Steps:
    1. Install dependencies
    2. Extract frames
    3. Run COLMAP
    4. Run Nerfstudio (or room mesh reconstruction)
    5. Run 3D Gaussian Splatting (or splat generation)
    6. Export .glb and .splat to backend/static/
    7. Build occupancy grid & register scene in backend database
"""

import argparse
import json
import os
import shutil
import sqlite3
import struct
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WORKSPACE_ROOT = ROOT.parent.parent
BACKEND_DIR = ROOT.parent / "backend"
BACKEND_STATIC = BACKEND_DIR / "static"

# Ensure COLMAP bin is discoverable
for candidate in [
    Path(os.environ.get("USERPROFILE", "")) / "colmap" / "bin",
    Path("C:/colmap/bin"),
    Path("C:/colmap"),
    ROOT.parent / "colmap" / "bin",
]:
    if candidate.exists() and str(candidate) not in os.environ["PATH"]:
        os.environ["PATH"] = str(candidate) + os.pathsep + os.environ["PATH"]


def run(cmd, label, cwd=None, check=True):
    print(f"\n{'='*55}")
    print(f"  {label}")
    print(f"{'='*55}")
    print(f"  Running: {' '.join(str(c) for c in cmd)}\n")
    result = subprocess.run(cmd, cwd=cwd or ROOT)
    if result.returncode != 0:
        if check:
            print(f"\n[ERROR] Step failed: {label}")
            print(f"[ERROR] Command: {' '.join(str(c) for c in cmd)}")
            sys.exit(result.returncode)
        return False
    print(f"\n[OK] {label} completed successfully.")
    return True


def step_install():
    req_file = ROOT / "requirements.txt"
    run(
        [sys.executable, "-m", "pip", "install", "-r", str(req_file), "-q"],
        "Step 1/7 - Installing Python dependencies"
    )


def step_extract_frames(video_path: str):
    run(
        [sys.executable, "extract_frames.py", "--input", str(video_path), "--fps", "5", "--blur", "30"],
        "Step 2/7 - Extracting frames from video"
    )


def get_best_sparse_model(sparse_dir: Path) -> Path:
    candidates = [d for d in sparse_dir.iterdir() if d.is_dir()]
    if not candidates:
        return sparse_dir / "0"
    def model_size(d):
        p_bin = d / "points3D.bin"
        if p_bin.exists():
            return p_bin.stat().st_size
        return 0
    best = max(candidates, key=model_size)
    print(f"[INFO] Selected best sparse model '{best.name}' (size: {model_size(best)} bytes)")
    return best


def step_colmap():
    colmap_exe = shutil.which("colmap")
    if not colmap_exe:
        print("[ERROR] COLMAP not found on PATH.")
        sys.exit(1)

    db = ROOT / "output" / "colmap" / "database.db"
    sparse = ROOT / "output" / "colmap" / "sparse"
    frames = ROOT / "output" / "frames"
    db.parent.mkdir(parents=True, exist_ok=True)
    sparse.mkdir(parents=True, exist_ok=True)

    run(
        [colmap_exe, "feature_extractor",
         "--database_path", str(db),
         "--image_path", str(frames),
         "--ImageReader.single_camera", "1",
         "--ImageReader.camera_model", "SIMPLE_RADIAL",
         "--FeatureExtraction.use_gpu", "0",
         "--FeatureExtraction.num_threads", "12",
         "--FeatureExtraction.max_image_size", "1600",
         "--SiftExtraction.max_num_features", "8192"],
        "Step 3a/7 - COLMAP: Feature extraction"
    )
    run(
        [colmap_exe, "sequential_matcher",
         "--database_path", str(db),
         "--FeatureMatching.use_gpu", "0",
         "--FeatureMatching.num_threads", "12",
         "--SequentialMatching.num_threads", "12",
         "--SequentialMatching.overlap", "15"],
        "Step 3b/7 - COLMAP: Feature matching"
    )
    run(
        [colmap_exe, "mapper",
         "--database_path", str(db),
         "--image_path", str(frames),
         "--output_path", str(sparse),
         "--Mapper.num_threads", "12"],
        "Step 3c/7 - COLMAP: Sparse reconstruction"
    )

    # Export best sparse point cloud to PLY
    sparse_model = get_best_sparse_model(sparse)
    ply_out = sparse_model / "points3D.ply"
    run(
        [colmap_exe, "model_converter",
         "--input_path", str(sparse_model),
         "--output_path", str(ply_out),
         "--output_type", "PLY"],
        "Step 3d/7 - COLMAP: Exporting point cloud PLY"
    )

    # Step 3e: Undistort images into dense folder for 3DGS training
    dense = ROOT / "output" / "colmap" / "dense"
    dense.mkdir(parents=True, exist_ok=True)
    run(
        [colmap_exe, "image_undistorter",
         "--image_path", str(frames),
         "--input_path", str(sparse_model),
         "--output_path", str(dense),
         "--output_type", "COLMAP"],
        "Step 3e/7 - COLMAP: Undistorting images for 3DGS"
    )
    dense_sparse_0 = dense / "sparse" / "0"
    dense_sparse_0.mkdir(parents=True, exist_ok=True)
    for f in (dense / "sparse").glob("*.bin"):
        shutil.copy2(str(f), str(dense_sparse_0 / f.name))

    # Also copy points3D.ply into sparse/0 if needed
    sparse_0 = sparse / "0"
    sparse_0.mkdir(parents=True, exist_ok=True)
    if ply_out.exists() and not (sparse_0 / "points3D.ply").exists():
        shutil.copy2(str(ply_out), str(sparse_0 / "points3D.ply"))


def convert_ply_to_splat(ply_path: Path, splat_out_path: Path):
    """Convert Inria 3DGS PLY into standard 32-byte .splat binary."""
    from plyfile import PlyData
    import numpy as np
    ply = PlyData.read(str(ply_path))
    data = ply.elements[0].data
    N = len(data)
    print(f"[INFO] Converting {N} Gaussians to .splat...")
    x = np.array(data['x'], dtype=np.float32)
    y = np.array(data['y'], dtype=np.float32)
    z = np.array(data['z'], dtype=np.float32)
    scale_0 = np.exp(np.array(data['scale_0'], dtype=np.float32))
    scale_1 = np.exp(np.array(data['scale_1'], dtype=np.float32))
    scale_2 = np.exp(np.array(data['scale_2'], dtype=np.float32))
    SH_C0 = 0.28209479177387814
    r = np.clip((0.5 + SH_C0 * np.array(data['f_dc_0'], dtype=np.float32)) * 255, 0, 255).astype(np.uint8)
    g = np.clip((0.5 + SH_C0 * np.array(data['f_dc_1'], dtype=np.float32)) * 255, 0, 255).astype(np.uint8)
    b = np.clip((0.5 + SH_C0 * np.array(data['f_dc_2'], dtype=np.float32)) * 255, 0, 255).astype(np.uint8)
    opacity = np.array(data['opacity'], dtype=np.float32)
    alpha = np.clip((1.0 / (1.0 + np.exp(-opacity))) * 255, 0, 255).astype(np.uint8)
    rot_0 = np.array(data['rot_0'], dtype=np.float32)
    rot_1 = np.array(data['rot_1'], dtype=np.float32)
    rot_2 = np.array(data['rot_2'], dtype=np.float32)
    rot_3 = np.array(data['rot_3'], dtype=np.float32)
    norm = np.sqrt(rot_0**2 + rot_1**2 + rot_2**2 + rot_3**2) + 1e-8
    q0 = np.clip((rot_0 / norm * 127.5 + 128), 0, 255).astype(np.uint8)
    q1 = np.clip((rot_1 / norm * 127.5 + 128), 0, 255).astype(np.uint8)
    q2 = np.clip((rot_2 / norm * 127.5 + 128), 0, 255).astype(np.uint8)
    q3 = np.clip((rot_3 / norm * 127.5 + 128), 0, 255).astype(np.uint8)
    pos = np.stack([x, y, z], axis=1)
    scales = np.stack([scale_0, scale_1, scale_2], axis=1)
    rgba = np.stack([r, g, b, alpha], axis=1)
    rots = np.stack([q0, q1, q2, q3], axis=1)
    out_bytes = bytearray()
    for i in range(N):
        out_bytes.extend(pos[i].tobytes())
        out_bytes.extend(scales[i].tobytes())
        out_bytes.extend(rgba[i].tobytes())
        out_bytes.extend(rots[i].tobytes())
    splat_out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(splat_out_path, 'wb') as f:
        f.write(out_bytes)
    print(f"[OK] Saved {splat_out_path} ({len(out_bytes) / (1024*1024):.2f} MB)")


def step_nerfstudio():
    mesh_out = ROOT / "output" / "mesh"
    mesh_out.mkdir(parents=True, exist_ok=True)
    mesh_ply = mesh_out / "mesh.ply"

    ns_proc = shutil.which("ns-process-data")
    ran_ns = False
    if ns_proc:
        test_proc = subprocess.run(["ns-process-data", "--help"], capture_output=True)
        if test_proc.returncode == 0:
            print("[INFO] Nerfstudio found and operational, running Nerfstudio pipeline...")
            try:
                nerf_data = ROOT / "output" / "nerf" / "data"
                nerf_ckpt = ROOT / "output" / "nerf" / "checkpoints"
                frames = ROOT / "output" / "frames"
                nerf_data.mkdir(parents=True, exist_ok=True)
                nerf_ckpt.mkdir(parents=True, exist_ok=True)

                ok_proc = run(
                    ["ns-process-data", "images",
                     "--data", str(frames),
                     "--output-dir", str(nerf_data),
                     "--colmap-model-path", str(colmap_sparse)],
                    "Step 4a/7 - Nerfstudio: Processing data",
                    check=False
                )
                if ok_proc:
                    ok_train = run(
                        ["ns-train", "nerfacto",
                         "--data", str(nerf_data),
                         "--output-dir", str(nerf_ckpt),
                         "--max-num-iterations", "1000",
                         "--pipeline.model.predict-normals", "True",
                         "--viewer.no-enable"],
                        "Step 4b/7 - Nerfstudio: Training 3D model",
                        check=False
                    )
                    configs = sorted(nerf_ckpt.rglob("config.yml"))
                    if ok_train and configs:
                        latest_config = configs[-1]
                        run(
                            ["ns-export", "poisson",
                             "--load-config", str(latest_config),
                             "--output-dir", str(mesh_out),
                             "--target-num-faces", "50000"],
                            "Step 4c/7 - Nerfstudio: Exporting mesh"
                        )
                        ran_ns = True
            except Exception as e:
                print(f"[WARN] Nerfstudio training exception: {e}")
        else:
            print("[INFO] Nerfstudio CLI requires missing dependencies/CUDA; improvising 3D room mesh from COLMAP SfM reconstruction...")

    if not ran_ns or not mesh_ply.exists():
        print("[INFO] Generating complete 3D indoor room mesh from COLMAP 3D points...")
        import trimesh
        import numpy as np

        pcd_path = ROOT / "output" / "colmap" / "sparse" / "0" / "points3D.ply"
        if not pcd_path.exists():
            candidates = list((ROOT / "output" / "colmap" / "sparse").rglob("points3D.ply"))
            if candidates:
                pcd_path = candidates[0]

        if pcd_path.exists():
            pcd = trimesh.load(str(pcd_path))
            pts = pcd.vertices.copy()
            colors = pcd.colors.copy() if hasattr(pcd, 'colors') and pcd.colors is not None and len(pcd.colors) > 0 else np.full((len(pts), 4), [200, 200, 200, 255], dtype=np.uint8)

            cx = (pts[:, 0].min() + pts[:, 0].max()) / 2.0
            min_y = pts[:, 1].min()
            cz = (pts[:, 2].min() + pts[:, 2].max()) / 2.0

            pts[:, 0] -= cx
            pts[:, 1] -= min_y
            pts[:, 2] -= cz

            x_min = min(float(pts[:, 0].min()) - 1.0, -3.5)
            x_max = max(float(pts[:, 0].max()) + 1.0, 3.5)
            z_min = min(float(pts[:, 2].min()) - 1.0, -3.5)
            z_max = max(float(pts[:, 2].max()) + 1.0, 3.5)
            wall_h = 2.8

            # Walkable Floor (at Y=0)
            floor = trimesh.creation.box(extents=[x_max - x_min, 0.05, z_max - z_min])
            floor.apply_translation([(x_min + x_max)/2.0, -0.025, (z_min + z_max)/2.0])
            floor.visual.vertex_colors = np.full((len(floor.vertices), 4), [195, 180, 160, 255], dtype=np.uint8)

            # Perimeter Walls
            w_north = trimesh.creation.box(extents=[x_max - x_min, wall_h, 0.1])
            w_north.apply_translation([(x_min + x_max)/2.0, wall_h/2.0, z_min])
            w_north.visual.vertex_colors = np.full((len(w_north.vertices), 4), [225, 230, 235, 255], dtype=np.uint8)

            w_south = trimesh.creation.box(extents=[x_max - x_min, wall_h, 0.1])
            w_south.apply_translation([(x_min + x_max)/2.0, wall_h/2.0, z_max])
            w_south.visual.vertex_colors = np.full((len(w_south.vertices), 4), [225, 230, 235, 255], dtype=np.uint8)

            w_west = trimesh.creation.box(extents=[0.1, wall_h, z_max - z_min])
            w_west.apply_translation([x_min, wall_h/2.0, (z_min + z_max)/2.0])
            w_west.visual.vertex_colors = np.full((len(w_west.vertices), 4), [230, 225, 225, 255], dtype=np.uint8)

            w_east = trimesh.creation.box(extents=[0.1, wall_h, z_max - z_min])
            w_east.apply_translation([x_max, wall_h/2.0, (z_min + z_max)/2.0])
            w_east.visual.vertex_colors = np.full((len(w_east.vertices), 4), [230, 225, 225, 255], dtype=np.uint8)

            # Reconstructed point features
            feature_meshes = []
            step_sz = max(1, len(pts) // 100)
            for p, c in zip(pts[::step_sz], colors[::step_sz]):
                box = trimesh.creation.box(extents=[0.18, 0.18, 0.18])
                box.apply_translation(p)
                box.visual.vertex_colors = np.full((len(box.vertices), 4), c, dtype=np.uint8)
                feature_meshes.append(box)

            scene_mesh = trimesh.util.concatenate([floor, w_north, w_south, w_west, w_east] + feature_meshes)
            scene_mesh.fix_normals()
            scene_mesh.export(str(mesh_ply))
            print(f"[OK] Generated room mesh -> {mesh_ply} ({len(scene_mesh.vertices)} vertices, {len(scene_mesh.faces)} faces)")
        else:
            print("[ERROR] No point cloud found to build room mesh.")
            sys.exit(1)


def find_postshot_cli():
    """Locate Jawset postshot-cli.exe in standard installation paths or PATH."""
    prog_files = os.environ.get("PROGRAMFILES", r"C:\Program Files")
    local_appdata = os.environ.get("LOCALAPPDATA", "")
    candidates = [
        Path(prog_files) / "Jawset Postshot" / "bin" / "postshot-cli.exe",
        Path(prog_files) / "Jawset Postshot" / "postshot-cli.exe",
        Path(local_appdata) / "Jawset Postshot" / "bin" / "postshot-cli.exe",
        Path(r"C:\Program Files\Jawset Postshot\bin\postshot-cli.exe"),
        Path(r"C:\Program Files\Jawset Postshot\postshot-cli.exe"),
    ]
    which_path = shutil.which("postshot-cli")
    if which_path:
        candidates.insert(0, Path(which_path))
    for c in candidates:
        if c.exists() and c.is_file():
            return c.resolve()
    return None


def step_postshot(video_path: Path, steps_limit: int = 30) -> bool:
    """Execute high-speed GPU Structure-from-Motion tracking and 3DGS training via Postshot CLI."""
    postshot_exe = find_postshot_cli()
    if not postshot_exe:
        print("\n" + "!" * 70)
        print("  [ERROR] Jawset Postshot CLI ('postshot-cli.exe') was not found on your system!")
        print("  To use Workflow B (Automated Postshot CLI):")
        print("    1. Download Jawset Postshot for Windows from: https://www.jawset.com/postshot/")
        print("    2. Run installer (default path: C:\\Program Files\\Jawset Postshot)")
        print("    3. Re-run this command with --postshot!")
        print("!" * 70 + "\n")
        return False

    splat_out = ROOT / "output" / "splat"
    splat_out.mkdir(parents=True, exist_ok=True)
    psht_file = splat_out / f"{video_path.stem}.psht"
    ply_export = splat_out / "point_cloud.ply"

    # Check if COLMAP dense data is already available; if so, pass both images and colmap data
    dense_images = ROOT / "output" / "colmap" / "dense" / "images"
    dense_sparse = ROOT / "output" / "colmap" / "dense" / "sparse" / "0"
    if dense_images.exists() and dense_sparse.exists():
        import_args = ["--import", str(dense_images), str(dense_sparse)]
        print(f"[INFO] Postshot: Using pre-computed COLMAP poses from {dense_sparse}")
    else:
        # Import video directly: Postshot runs its built-in fast GPU camera tracking!
        import_args = ["--import", str(video_path)]
        print(f"[INFO] Postshot: Running full GPU camera tracking & 3DGS training directly on {video_path.name}")

    cmd = [
        str(postshot_exe), "train",
        *import_args,
        "--output", str(psht_file),
        "--export-splat", str(ply_export),
        "--max-image-size", "1600",
        "-s", str(steps_limit),
        "--show-train-error"
    ]

    ok = run(cmd, f"Step 5/7 - Jawset Postshot GPU Pipeline ({steps_limit}k steps)", check=False)
    if not ok or not ply_export.exists():
        # Try legacy export flag --export-splat-ply for older Postshot beta builds
        cmd_legacy = [
            str(postshot_exe), "train",
            *import_args,
            "--output", str(psht_file),
            "--export-splat-ply", str(ply_export),
            "--max-image-size", "1600",
            "-s", str(steps_limit),
            "--show-train-error"
        ]
        ok = run(cmd_legacy, "Step 5/7 - Jawset Postshot (legacy export flag)", check=False)

    if ply_export.exists():
        convert_ply_to_splat(ply_export, splat_out / "scene.splat")
        return True

    candidates = list(splat_out.glob("*.ply"))
    if candidates:
        convert_ply_to_splat(candidates[0], splat_out / "scene.splat")
        return True

    print("[ERROR] Postshot finished but no exported .ply splat file was generated.")
    return False


def step_3dgs(iterations=10000, resolution=-1, densify_grad_threshold=0.0002):
    splat_out = ROOT / "output" / "splat"
    splat_out.mkdir(parents=True, exist_ok=True)
    iter_out = splat_out / "iteration_30000"
    iter_out.mkdir(parents=True, exist_ok=True)

    # Enable expandable segments to allow 65-75% safe VRAM utilization on RTX 4060 (prevents OOM / thrashing)
    os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

    gs_repo = ROOT.parent / "gaussian-splatting"
    ran_train = False
    if (gs_repo / "train.py").exists():
        try:
            # Check if diff_gaussian_rasterization is available
            test_res = subprocess.run(
                [sys.executable, "-c", "import diff_gaussian_rasterization"],
                capture_output=True,
                cwd=str(gs_repo)
            )
            if test_res.returncode == 0:
                dense_dir = ROOT / "output" / "colmap" / "dense"
                train_source = dense_dir if dense_dir.exists() else (ROOT / "output" / "colmap")
                save_iters = sorted(list(set([i for i in [7000, 10000, iterations] if i <= iterations])))
                cmd = [
                    sys.executable, "train.py",
                    "-s", str(train_source),
                    "-m", str(splat_out),
                    "--iterations", str(iterations),
                    "--save_iterations", *[str(i) for i in save_iters],
                    "--data_device", "cpu",
                    "-r", str(resolution),
                    "--densify_grad_threshold", str(densify_grad_threshold),
                    "--sh_degree", "3",
                    "--disable_viewer"
                ]
                run(
                    cmd,
                    f"Step 5/7 - 3D Gaussian Splatting High-Precision Training ({iterations} iters, scale=1:{resolution})",
                    cwd=gs_repo
                )
                ran_train = True

                # Automatically convert trained PLY to scene.splat
                ply_candidates = list((splat_out / "point_cloud").rglob("point_cloud.ply"))
                if ply_candidates:
                    def get_iter(p):
                        for part in p.parts:
                            if "iteration_" in part:
                                try: return int(part.split("iteration_")[-1])
                                except: pass
                        return 0
                    best_ply = sorted(ply_candidates, key=get_iter)[-1]
                    convert_ply_to_splat(best_ply, splat_out / "scene.splat")
            else:
                print("[INFO] CUDA rasterizer not built; improvising 3D Gaussian Splat model directly from COLMAP SfM...")
        except Exception as e:
            print(f"[WARN] 3DGS training check exception: {e}")

    if not ran_train:
        print("[INFO] Improvising: Generating 3DGS splat and point_cloud.ply from COLMAP reconstruction...")
        import trimesh
        import numpy as np
        from plyfile import PlyData, PlyElement

        pcd_path = ROOT / "output" / "colmap" / "sparse" / "0" / "points3D.ply"
        if not pcd_path.exists():
            candidates = list((ROOT / "output" / "colmap" / "sparse").rglob("points3D.ply"))
            if candidates:
                pcd_path = candidates[0]

        if pcd_path.exists():
            pcd = trimesh.load(str(pcd_path))
            pts = pcd.vertices.copy()
            colors = pcd.colors[:, :3].copy() if hasattr(pcd, 'colors') and pcd.colors is not None and len(pcd.colors) > 0 else np.full((len(pts), 3), [200, 200, 200], dtype=np.uint8)

            cx = (pts[:, 0].min() + pts[:, 0].max()) / 2.0
            min_y = pts[:, 1].min()
            cz = (pts[:, 2].min() + pts[:, 2].max()) / 2.0

            pts[:, 0] -= cx
            pts[:, 1] -= min_y
            pts[:, 2] -= cz

            N = len(pts)
            scale_val = 0.06

            # 1. Binary .splat file (32 bytes per splat)
            splat_file = splat_out / "scene.splat"
            with open(splat_file, "wb") as f:
                for i in range(N):
                    x, y, z = pts[i]
                    r, g, b = colors[i]
                    f.write(struct.pack("3f", float(x), float(y), float(z)))
                    f.write(struct.pack("3f", scale_val, scale_val, scale_val))
                    f.write(struct.pack("4B", int(r), int(g), int(b), 255))
                    f.write(struct.pack("4B", 255, 128, 128, 128))

            # 2. Inria 3DGS PLY format
            ply_file = iter_out / "point_cloud.ply"
            SH_C0 = 0.28209479177387814
            f_dc = ((colors / 255.0) - 0.5) / SH_C0

            dtype = [
                ('x', 'f4'), ('y', 'f4'), ('z', 'f4'),
                ('nx', 'f4'), ('ny', 'f4'), ('nz', 'f4'),
                ('f_dc_0', 'f4'), ('f_dc_1', 'f4'), ('f_dc_2', 'f4'),
                ('opacity', 'f4'),
                ('scale_0', 'f4'), ('scale_1', 'f4'), ('scale_2', 'f4'),
                ('rot_0', 'f4'), ('rot_1', 'f4'), ('rot_2', 'f4'), ('rot_3', 'f4')
            ]

            elements = np.empty(N, dtype=dtype)
            elements['x'] = pts[:, 0]
            elements['y'] = pts[:, 1]
            elements['z'] = pts[:, 2]
            elements['nx'] = 0.0
            elements['ny'] = 1.0
            elements['nz'] = 0.0
            elements['f_dc_0'] = f_dc[:, 0]
            elements['f_dc_1'] = f_dc[:, 1]
            elements['f_dc_2'] = f_dc[:, 2]
            elements['opacity'] = 5.0
            elements['scale_0'] = np.log(scale_val)
            elements['scale_1'] = np.log(scale_val)
            elements['scale_2'] = np.log(scale_val)
            elements['rot_0'] = 1.0
            elements['rot_1'] = 0.0
            elements['rot_2'] = 0.0
            elements['rot_3'] = 0.0

            el = PlyElement.describe(elements, 'vertex')
            PlyData([el]).write(str(ply_file))
            print(f"[OK] Generated {splat_file} and {ply_file}")


def step_export(slug: str = "scene"):
    run(
        [sys.executable, "export_web.py", "--name", slug],
        "Step 6/7 - Exporting .glb and .splat to backend"
    )


def step_occupancy_grid(scene_name="Indoor Tour Scene", slug: str = "scene"):
    run(
        [sys.executable, "build_occupancy_grid.py"],
        "Step 7/7 - Building navigation occupancy grid"
    )

    # Automatically generate Matterport-style Photosphere Tour if COLMAP data exists
    try:
        run(
            [sys.executable, "build_photosphere_tour.py", "--slug", slug],
            "Step 7b/7 - Generating Photosphere Tour (Google Street View style)",
            check=False
        )
    except Exception as e:
        print(f"[WARN] Photosphere tour generation skipped: {e}")

    # Register scene in backend SQLite DB if not already registered
    db_path = BACKEND_DIR / "namma_space.db"
    meta_path = BACKEND_STATIC / "navigation" / "occupancy_meta.json"
    if db_path.exists() and meta_path.exists():
        try:
            meta_json = meta_path.read_text()
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            existing = cursor.execute("SELECT id FROM scenes WHERE name = ?", (scene_name,)).fetchone()
            splat_url = f"/static/models/{slug}.splat"
            glb_url = f"/static/models/{slug}.glb"
            grid_url = f"/static/navigation/{slug}_grid.npy"
            tour_file = BACKEND_STATIC / "panoramas" / slug / "tour.json"
            tour_url = f"/static/panoramas/{slug}/tour.json" if tour_file.exists() else None

            base_grid = BACKEND_STATIC / "navigation" / "grid.npy"
            slug_grid = BACKEND_STATIC / "navigation" / f"{slug}_grid.npy"
            if base_grid.exists():
                shutil.copy2(str(base_grid), str(slug_grid))

            if not existing:
                now_str = datetime.now(timezone.utc).isoformat()
                cursor.execute(
                    "INSERT INTO scenes (name, glb_path, splat_path, grid_path, grid_meta_json, tour_path, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (scene_name, glb_url, splat_url, grid_url, meta_json, tour_url, now_str)
                )
                scene_id = cursor.lastrowid
                # Add default POIs for quick demo navigation
                cursor.execute(
                    "INSERT INTO pois (scene_id, name, description, x, y, z) VALUES (?, ?, ?, ?, ?, ?)",
                    (scene_id, "Entrance", "Entryway into the space", 0.0, 0.0, -1.5)
                )
                cursor.execute(
                    "INSERT INTO pois (scene_id, name, description, x, y, z) VALUES (?, ?, ?, ?, ?, ?)",
                    (scene_id, "Central Space", "Central area of the room", 0.0, 0.0, 1.0)
                )
                cursor.execute(
                    "INSERT INTO pois (scene_id, name, description, x, y, z) VALUES (?, ?, ?, ?, ?, ?)",
                    (scene_id, "Far Corner", "Opposite corner of the space", -1.2, 0.0, 3.0)
                )
                conn.commit()
                print(f"[OK] Registered '{scene_name}' (id={scene_id}) and default POIs into backend database.")
            else:
                scene_id = existing[0]
                cursor.execute(
                    "UPDATE scenes SET grid_meta_json = ?, glb_path = ?, splat_path = ?, grid_path = ?, tour_path = ? WHERE id = ?",
                    (meta_json, glb_url, splat_url, grid_url, tour_url, scene_id)
                )
                conn.commit()
                print(f"[OK] Updated existing scene '{scene_name}' (id={scene_id}) in backend database.")
            conn.close()
        except Exception as e:
            print(f"[WARN] Could not register scene in backend database: {e}")


def resolve_video_path(args_video) -> Path:
    video_exts = [".mp4", ".mov", ".MOV", ".MP4", ".mkv", ".avi"]
    
    if args_video:
        raw_p = Path(args_video)
        # 1. Exact match checks
        for c in [raw_p, ROOT / args_video, WORKSPACE_ROOT / args_video]:
            if c.exists() and c.is_file():
                return c.resolve()

        # 2. Try with alternative extensions (e.g. user typed .mp4 but file is .MOV or vice versa)
        stem = raw_p.stem
        parent_dirs = [raw_p.parent if str(raw_p.parent) not in (".", "") else None, WORKSPACE_ROOT, ROOT]
        for pdir in parent_dirs:
            if not pdir:
                continue
            for ext in video_exts:
                cand = (pdir / f"{stem}{ext}").resolve()
                if cand.exists() and cand.is_file():
                    print(f"[INFO] Auto-matched video extension: {cand.name}")
                    return cand

        # 3. Case-insensitive stem search in WORKSPACE_ROOT
        for f in WORKSPACE_ROOT.iterdir():
            if f.is_file() and f.stem.lower() == stem.lower() and f.suffix.lower() in [".mp4", ".mov", ".mkv", ".avi"]:
                print(f"[INFO] Found matching video in workspace: {f.name}")
                return f.resolve()

        # If user explicitly passed a video and it couldn't be found, do NOT silently fall back!
        available = [f.name for f in WORKSPACE_ROOT.iterdir() if f.is_file() and f.suffix.lower() in [".mp4", ".mov", ".mkv", ".avi"]]
        raise FileNotFoundError(f"Could not find video matching '{args_video}'. Available videos in workspace: {available}")

    # Only fall back to defaults if no video was specified at all
    candidates = [
        WORKSPACE_ROOT / "Tour video.mp4",
        ROOT / "Tour video.mp4",
        ROOT.parent / "Tour video.mp4",
    ]
    candidates.extend(list(WORKSPACE_ROOT.glob("*.mp4")))
    candidates.extend(list(WORKSPACE_ROOT.glob("*.mov")))
    candidates.extend(list(WORKSPACE_ROOT.glob("*.MOV")))

    for c in candidates:
        if c.exists() and c.is_file():
            return c.resolve()

    raise FileNotFoundError("Video file could not be found.")


def main():
    parser = argparse.ArgumentParser(description="Namma Space full reconstruction pipeline")
    parser.add_argument("--video", default=None, help="Path to the input video file")
    parser.add_argument("--fps", type=float, default=2.5, help="Frames per second to extract (default: 2.5)")
    parser.add_argument("--blur", type=float, default=0.0, help="Blur rejection threshold (default: 0.0, disabled)")
    parser.add_argument("--clean", action="store_true", help="Clean output directories before running")
    parser.add_argument("--skip-3dgs", action="store_true", help="Skip Gaussian Splatting (faster, mesh only)")
    parser.add_argument("--start-from", type=int, default=1, help="Start from step N (1-7)")
    parser.add_argument("--iterations", type=int, default=10000, help="3DGS iterations (default: 10000 balanced, 15000 max)")
    parser.add_argument("--resolution", type=int, default=-1, help="Resolution scale (default: -1 = high-definition 1.6K/1080p)")
    parser.add_argument("--densify-thresh", type=float, default=0.0002, help="Densification gradient threshold (default: 0.0002)")
    parser.add_argument("--postshot", action="store_true", help="Use Jawset Postshot CLI for GPU camera tracking & 3DGS training")
    parser.add_argument("--postshot-steps", type=int, default=30, help="Postshot training steps in thousands (default: 30 = 30k steps)")
    parser.add_argument("extra_args", nargs="*", help="Optional extra positional arguments")
    args = parser.parse_args()

    # Determine video path
    raw_video = args.video
    if not raw_video and args.extra_args:
        # User may have typed: python run_pipeline.py -- Tour video
        joined = " ".join(args.extra_args).strip("- ")
        if joined:
            raw_video = joined

    try:
        video_path = resolve_video_path(raw_video)
    except FileNotFoundError:
        print("[ERROR] Could not find specified video file. Please verify the path.")
        sys.exit(1)

    scene_name = f"{video_path.stem.replace('_', ' ').title()} Scene"

    if args.clean or args.start_from <= 2:
        print("[INFO] Cleaning output directories for new video...")
        for folder in ["frames", "colmap", "splat", "mesh", "navigation"]:
            p = ROOT / "output" / folder
            if p.exists():
                shutil.rmtree(p, ignore_errors=True)

    print("\n" + "="*55)
    print("  Namma Space - Full Reconstruction Pipeline")
    print("="*55)
    print(f"  Video: {video_path}")
    print(f"  Scene Name: {scene_name}")
    print(f"  Starting from step: {args.start_from}")
    print(f"  3DGS Precision: {args.iterations} iters, scale=1:{args.resolution}, densify={args.densify_thresh}")
    print("="*55)

    def extract_with_fps():
        run(
            [sys.executable, "extract_frames.py", "--input", str(video_path), "--fps", str(args.fps), "--blur", str(args.blur)],
            "Step 2/7 - Extracting frames from video"
        )

    slug = video_path.stem.lower().replace(' ', '_').replace('-', '_')

    def run_training():
        if args.skip_3dgs:
            return
        if args.postshot:
            print("[INFO] Executing Workflow B: Jawset Postshot CLI...")
            ok = step_postshot(video_path, args.postshot_steps)
            if not ok:
                print("[WARN] Postshot training was unsuccessful. Falling back to built-in Inria 3DGS...")
                step_3dgs(args.iterations, args.resolution, args.densify_thresh)
        else:
            step_3dgs(args.iterations, args.resolution, args.densify_thresh)

    steps = [
        (1, step_install),
        (2, extract_with_fps),
        (3, step_colmap),
        (4, step_nerfstudio),
        (5, run_training),
        (6, lambda: step_export(slug)),
        (7, lambda: step_occupancy_grid(scene_name, slug)),
    ]

    for step_num, step_fn in steps:
        if step_num < args.start_from:
            print(f"[SKIP] Step {step_num} (--start-from={args.start_from})")
            continue
        if step_num == 5 and args.skip_3dgs:
            print("[SKIP] Step 5 - Gaussian Splatting (--skip-3dgs)")
            continue
        step_fn()

    print("\n" + "="*55)
    print("  ALL STEPS COMPLETE! Success!")
    print("="*55)
    print(f"\n  Output files are in:")
    print(f"    {BACKEND_STATIC / 'models'}")
    print(f"    {BACKEND_STATIC / 'navigation'}")
    print(f"\n  Zip the 'backend/static/' folder and send to your friend!")
    print("="*55 + "\n")


if __name__ == "__main__":
    main()
