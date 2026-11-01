"""
pipeline/stages/splat.py
────────────────────────
Stage (Optional): 3D Gaussian Splatting Training.
Preserves 3DGS as an optional photoreal visual mode tab without breaking core pipeline.
"""

from pathlib import Path
import shutil
import struct
import subprocess
import sys
from typing import Any, Dict
import numpy as np

from .base import BaseStage
from ..config import PipelineConfig


def convert_ply_to_splat(ply_path: Path, splat_out_path: Path) -> None:
    """Convert Inria 3DGS PLY into standard 32-byte .splat binary."""
    from plyfile import PlyData
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


class SplatStage(BaseStage):
    def __init__(self):
        super().__init__(
            name="splat",
            description="Train 3D Gaussian Splats (optional photoreal mode)",
        )

    def is_cached(self, out_dir: Path, config: PipelineConfig) -> bool:
        splat_file = out_dir / "splat" / "scene.splat"
        return splat_file.exists() and splat_file.stat().st_size > 0

    def execute(
        self,
        input_path: Path,
        out_dir: Path,
        config: PipelineConfig,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        if not config.photoreal_splat.enabled:
            print("[INFO] 3DGS photoreal mode disabled in config. Skipping.")
            return context

        dense_dir = out_dir / "colmap" / "dense"
        if not dense_dir.exists():
            dense_dir = out_dir / "colmap"

        splat_out = out_dir / "splat"
        splat_out.mkdir(parents=True, exist_ok=True)
        gs_repo = Path(__file__).resolve().parent.parent.parent / "gaussian-splatting"
        train_py = gs_repo / "train.py"

        if not train_py.exists():
            print(f"[WARN] 3DGS train.py not found at {train_py}. Skipping.")
            return context

        iters = str(config.photoreal_splat.iterations)
        r_scale = str(config.photoreal_splat.resolution_scale)
        device = config.photoreal_splat.data_device
        densify_thresh = str(config.photoreal_splat.densify_grad_threshold)
        sh_deg = str(config.photoreal_splat.sh_degree)

        # Allow 80-90% safe VRAM allocation on Windows without heap fragmentation
        os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

        cmd = [
            sys.executable, str(train_py),
            "-s", str(dense_dir),
            "-m", str(splat_out),
            "--iterations", iters,
            "--save_iterations", iters,
            "--data_device", device,
            "-r", r_scale,
            "--densify_grad_threshold", densify_thresh,
            "--sh_degree", sh_deg,
            "--disable_viewer",
        ]
        print(f"\n--- Launching 3DGS High-Precision Training ({iters} iters, scale=1:{r_scale}, densify_thresh={densify_thresh}) ---")
        res = subprocess.run(cmd, cwd=str(gs_repo))
        if res.returncode == 0:
            ply_candidates = list((splat_out / "point_cloud").rglob("point_cloud.ply"))
            if ply_candidates:
                convert_ply_to_splat(ply_candidates[-1], splat_out / "scene.splat")
        else:
            print(f"[WARN] 3DGS training exited with code {res.returncode}")

        return context

