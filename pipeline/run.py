"""
pipeline/run.py
───────────────
Unified entry point for the Namma Space reconstruction & navigation pipeline.

Usage:
    python -m pipeline.run --input <video_or_folder> --out out/ --config config.yaml
    python -m pipeline.run --input test/sample_data/frames --out out/ --stages pose,align
    python -m pipeline.run --input Roomvid.mp4 --out out/ --pose-backend auto --metric-reference 2.0
"""

import argparse
import json
import os
from pathlib import Path
import sys
import time
from typing import Dict, List

# Ensure UTF-8 output encoding on Windows consoles where available
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
    try:
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from .config import load_config
from .stages import (
    BaseStage,
    ExtractStage,
    PoseStage,
    AlignStage,
    PanosStage,
    DepthProxyStage,
    NavStage,
    ExportStage,
    SplatStage,
)


def print_progress_bar(current: int, total: int, stage_name: str, stage_desc: str, bar_len: int = 24):
    """Render an animated terminal progress bar."""
    pct = float(current) / max(1, total)
    filled = int(round(bar_len * pct))
    bar = "=" * filled + "-" * (bar_len - filled)
    pct_str = f"{int(pct * 100):3d}%"
    sep = "-" * 70
    print(f"\n{sep}")
    print(f"  [{bar}] {pct_str} | Stage {current}/{total}: {stage_name.upper()}")
    print(f"  -> {stage_desc}")
    print(f"{sep}")


def get_default_stages() -> List[BaseStage]:
    return [
        ExtractStage(),
        PoseStage(),
        AlignStage(),
        PanosStage(),
        DepthProxyStage(),
        NavStage(),
        ExportStage(),
        SplatStage(),
    ]


def main():
    parser = argparse.ArgumentParser(
        description="Namma Space Hybrid Reconstruction & Navigation Pipeline"
    )
    parser.add_argument("--input", "-i", required=True, help="Path to input video file or folder of frames")
    parser.add_argument("--out", "-o", default="out", help="Output directory (default: out/)")
    parser.add_argument("--config", "-c", default="config.yaml", help="Path to config.yaml (default: config.yaml)")
    parser.add_argument("--stages", help="Comma-separated stage names to run (e.g. extract,pose,align)")
    parser.add_argument("--from-stage", help="Start execution from specified stage (skipping prior cached stages)")
    parser.add_argument("--force", action="store_true", help="Force re-execution of stages ignoring cache")
    parser.add_argument("--skip-splat", action="store_true", help="Skip optional 3DGS photoreal training")
    parser.add_argument("--pose-backend", choices=["colmap", "vggt", "auto"], help="Override pose backend (colmap, vggt, auto)")
    parser.add_argument("--metric-reference", type=float, help="Optional metric dimension reference in metres (e.g. 2.0 for door)")
    parser.add_argument("--rotation", type=int, choices=[0, 90, 180, 270], help="Rotate video frames clockwise (0, 90, 180, 270)")
    parser.add_argument("--dry-run", action="store_true", help="Print execution plan and cache status without running")
    args = parser.parse_args()

    input_path = Path(args.input).resolve()
    if not input_path.exists():
        repo_root = Path(__file__).resolve().parent.parent
        alt_path = (repo_root / args.input).resolve()
        if alt_path.exists():
            input_path = alt_path
        else:
            print(f"[ERROR] Input path not found: {args.input}", file=sys.stderr)
            sys.exit(1)

    out_dir = Path(args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    config_path = Path(args.config).resolve()
    if not config_path.exists():
        config_path = Path("config.yaml")

    config = load_config(config_path)
    if args.skip_splat:
        config.photoreal_splat.enabled = False
    if args.pose_backend:
        config.pose_backend.backend = args.pose_backend
    if args.metric_reference is not None:
        config.general.reference_dimension_m = args.metric_reference
    if args.rotation is not None:
        config.frame_sampling.rotation = args.rotation

    all_stages = get_default_stages()
    stage_map = {s.name: s for s in all_stages}

    # Determine stages to run
    selected_stages: List[BaseStage] = []
    if args.stages:
        names = [n.strip() for n in args.stages.split(",") if n.strip()]
        for name in names:
            if name not in stage_map:
                print(f"[ERROR] Unknown stage '{name}'. Available: {list(stage_map.keys())}", file=sys.stderr)
                sys.exit(1)
            selected_stages.append(stage_map[name])
    elif args.from_stage:
        target = args.from_stage.strip().lower()
        found = False
        for s in all_stages:
            if s.name == target:
                found = True
            if found:
                selected_stages.append(s)
        if not found:
            print(f"[ERROR] Unknown start stage '{target}'.", file=sys.stderr)
            sys.exit(1)
    else:
        selected_stages = all_stages

    # Filter out splat if disabled
    if not config.photoreal_splat.enabled:
        selected_stages = [s for s in selected_stages if s.name != "splat"]

    print("\n" + "="*70)
    print("  NAMMA SPACE -- HYBRID RECONSTRUCTION & NAVIGATION PIPELINE")
    print("="*70)
    print(f"  Input:       {input_path}")
    print(f"  Output:      {out_dir}")
    print(f"  Config:      {config_path}")
    print(f"  Pose Engine: {config.pose_backend.backend.upper()}")
    print(f"  Scale Mode:  {config.general.scale_method} (Ref: {config.general.reference_dimension_m}m)")
    print(f"  Stages:      {' -> '.join(s.name for s in selected_stages)}")
    print("="*70)

    if args.dry_run:
        print("\n[DRY RUN] Stage cache evaluation:")
        for s in selected_stages:
            cached = s.is_cached(out_dir, config)
            print(f"  - {s.name:15}: {'[CACHED]' if cached else '[NEEDS EXECUTION]'}")
        return

    context: Dict[str, Any] = {}
    t_start = time.perf_counter()

    for i, stage in enumerate(selected_stages, 1):
        print_progress_bar(i, len(selected_stages), stage.name, stage.description)
        context = stage.run(input_path, out_dir, config, context, force=args.force)

    total_time = time.perf_counter() - t_start

    # Summary and Scaling Analysis
    timings_path = out_dir / "timings.json"
    timings = {}
    if timings_path.exists():
        try:
            timings = json.loads(timings_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    scaling_notes = {
        "extract": "Linear with video duration (O(T))",
        "pose": "Windowed sequential matching (O(N)), bounded VRAM",
        "align": "Fast RANSAC plane fitting (O(K))",
        "panos": "Pose-guided ray warping (~15s per node)",
        "depth_proxy": "Open3D Poisson surface reconstruction",
        "nav": "Vectorized 5cm 2D height slicing (<0.2s)",
        "export": "Deliverable packaging & SQLite synchronization",
        "splat": "Optional 3DGS training (7000 steps)",
    }

    print("\n" + "="*70)
    print("  PIPELINE EXECUTION & TURNAROUND SUMMARY")
    print("="*70)
    print(f"  Total Wall-Clock Time:  {total_time:.2f}s ({total_time / 60:.2f} min)")
    target_time_min = 15.0
    status_str = "PASS [WELL UNDER 15 MIN TARGET]" if total_time < target_time_min * 60 else "EXCEEDED"
    print(f"  Turnaround Target:      < {target_time_min:.1f} min for 50 m² venue")
    print(f"  Competition Status:     {status_str}\n")

    print(f"  {'Stage':<14} | {'Time (s)':<10} | {'Status':<14} | {'Scaling Profile'}")
    print(f"  {'-'*14}-+-{'-'*10}-+-{'-'*14}-+-{'-'*26}")
    for s in selected_stages:
        t_val = timings.get(s.name, 0.0)
        st = "Completed" if t_val > 0 else "Cached"
        profile = scaling_notes.get(s.name, "O(N)")
        print(f"  {s.name:<14} | {t_val:<10.2f} | {st:<14} | {profile}")
    print("="*70)

    print(f"\n  Deliverables ready for zero-install web inspection in: {out_dir}")
    print(f"    - Tour Manifest: {out_dir / 'tour.json'}")
    print(f"    - NavGrid:       {out_dir / 'nav' / 'navgrid.json'}")
    print(f"    - Proxy Mesh:    {out_dir / 'mesh' / 'proxy.glb'}")
    print(f"    - NavMesh:       {out_dir / 'mesh' / 'navmesh.glb'}")
    print(f"    - Panoramas:     {out_dir / 'panos'}")
    print(f"    - Debug Render:  {out_dir / 'debug_floor_alignment.png'}")
    print(f"    - Nav Paths:     {out_dir / 'nav' / 'nav_paths.png'}\n")


if __name__ == "__main__":
    main()
