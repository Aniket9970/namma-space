#!/usr/bin/env python3
"""
extract_frames.py
─────────────────
Extract frames from a video file at a configurable FPS, discarding blurry
frames based on the Laplacian variance threshold.

Usage:
    python extract_frames.py --input path/to/video.mp4 [options]

Options:
    --input    Path to input video file (required)
    --output   Output directory for frames (default: output/frames)
    --fps      Target extraction rate in frames-per-second (default: 2)
    --blur     Laplacian variance threshold; frames below this are skipped (default: 100)
"""

import argparse
import os
import sys
from pathlib import Path

import cv2
import numpy as np
from tqdm import tqdm


def is_blurry(frame: np.ndarray, threshold: float) -> bool:
    """Return True if the Laplacian variance of the frame is below threshold."""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    variance = cv2.Laplacian(gray, cv2.CV_64F).var()
    return variance < threshold


def extract_frames(
    input_path: str,
    output_dir: str = "output/frames",
    fps: float = 2.0,
    blur_threshold: float = 100.0,
) -> None:
    cap = cv2.VideoCapture(input_path)
    if not cap.isOpened():
        print(f"[ERROR] Cannot open video: {input_path}", file=sys.stderr)
        sys.exit(1)

    video_fps: float = cap.get(cv2.CAP_PROP_FPS)
    total_frames: int = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration: float = total_frames / video_fps if video_fps > 0 else 0

    print(f"[INFO] Video: {input_path}")
    print(f"[INFO] Native FPS: {video_fps:.2f}, total frames: {total_frames}, duration: {duration:.1f}s")
    print(f"[INFO] Extracting at {fps} FPS, blur threshold: {blur_threshold}")

    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    # Interval in source frames between extractions
    frame_interval = max(1, int(round(video_fps / fps)))

    saved = 0
    skipped_blur = 0
    frame_idx = 0

    with tqdm(total=total_frames, desc="Processing frames", unit="fr") as pbar:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_idx % frame_interval == 0:
                if is_blurry(frame, blur_threshold):
                    skipped_blur += 1
                else:
                    filename = out_path / f"frame_{saved:06d}.jpg"
                    cv2.imwrite(str(filename), frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
                    saved += 1

            frame_idx += 1
            pbar.update(1)

    cap.release()

    print(f"\n[DONE] Saved {saved} frames -> {out_path}")
    print(f"       Skipped {skipped_blur} blurry frames (threshold={blur_threshold})")
    if saved == 0:
        print("[WARN] No frames passed blur threshold. Re-extracting all target frames without blur filter...")
        cap = cv2.VideoCapture(input_path)
        frame_idx = 0
        saved = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            if frame_idx % frame_interval == 0:
                filename = out_path / f"frame_{saved:06d}.jpg"
                cv2.imwrite(str(filename), frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
                saved += 1
            frame_idx += 1
        cap.release()
        print(f"[OK] Fallback extracted {saved} frames -> {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract frames from a video, skipping blurry ones."
    )
    parser.add_argument("--input", required=True, help="Path to input video file")
    parser.add_argument(
        "--output", default="output/frames", help="Output directory (default: output/frames)"
    )
    parser.add_argument(
        "--fps", type=float, default=2.0, help="Target frames per second to extract (default: 2)"
    )
    parser.add_argument(
        "--blur",
        type=float,
        default=100.0,
        help="Laplacian variance threshold for blur detection (default: 100)",
    )
    args = parser.parse_args()
    extract_frames(args.input, args.output, args.fps, args.blur)


if __name__ == "__main__":
    main()
