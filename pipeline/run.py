"""
pipeline/run.py
───────────────
Unified entry point for the Namma Space reconstruction & navigation pipeline.

Usage:
    python -m pipeline.run --input <video_or_folder> --out out/ --config config.yaml
    python -m pipeline.run --input test/sample_data/frames --out out/ --stages pose,align
    python -m pipeline.run --input Roomvid.mp4 --out out/ --from-stage panos
"""

import argparse
import json
import os
from pathlib import Path
import sys
import time
from typing import Dict, List

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
    parser.add_argument("--dry-run", action="store_true", help="Print execution plan and cache status without running")
    args = parser.parse_args()

    input_path = Path(args.input).resolve()
    if not input_path.exists():
        # Check relative to repo root
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

    print("\n" + "="*65)
    print("  NAMMA SPACE — HYBRID RECONSTRUCTION & NAVIGATION PIPELINE")
    print("="*65)
    print(f"  Input:   {input_path}")
    print(f"  Output:  {out_dir}")
    print(f"  Config:  {config_path}")
    print(f"  Stages:  {' -> '.join(s.name for s in selected_stages)}")
    print("="*65 + "\n")

    if args.dry_run:
        print("[DRY RUN] Stage cache evaluation:")
        for s in selected_stages:
            cached = s.is_cached(out_dir, config)
            print(f"  - {s.name:15}: {'[CACHED]' if cached else '[NEEDS EXECUTION]'}")
        return

    context: Dict[str, Any] = {}
    t_start = time.perf_counter()

    for stage in selected_stages:
        context = stage.run(input_path, out_dir, config, context, force=args.force)

    total_time = time.perf_counter() - t_start

    # Print summary table
    timings_path = out_dir / "timings.json"
    timings = {}
    if timings_path.exists():
        try:
            timings = json.loads(timings_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    print("\n" + "="*65)
    print("  PIPELINE EXECUTION SUMMARY")
    print("="*65)
    print(f"  Total pipeline wall-clock time: {total_time:.2f}s\n")
    print(f"  {'Stage':<20} | {'Time (s)':<12} | {'Status':<15}")
    print(f"  {'-'*20}-+-{'-'*12}-+-{'-'*15}")
    for s in selected_stages:
        t_val = timings.get(s.name, 0.0)
        status = "Completed" if t_val > 0 else "Cached/Skipped"
        print(f"  {s.name:<20} | {t_val:<12.2f} | {status:<15}")
    print("="*65)
    print(f"\n  Final artifacts available in: {out_dir}")
    print(f"    - Tour Manifest: {out_dir / 'tour.json'}")
    print(f"    - NavGrid:       {out_dir / 'nav' / 'navgrid.json'}")
    print(f"    - Proxy Mesh:    {out_dir / 'mesh' / 'proxy.glb'}")
    print(f"    - NavMesh:       {out_dir / 'mesh' / 'navmesh.glb'}")
    print(f"    - Panoramas:     {out_dir / 'panos'}")
    print("="*65 + "\n")


if __name__ == "__main__":
    main()
