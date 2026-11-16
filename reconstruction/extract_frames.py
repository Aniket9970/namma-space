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


def is_blurry(gray: np.ndarray, threshold: float) -> bool:
    """Return True if the Laplacian variance of the frame is below threshold."""
    if threshold <= 0:
        return False
    variance = cv2.Laplacian(gray, cv2.CV_64F).var()
    return variance < threshold


def is_textureless(gray: np.ndarray, threshold: float = 12.0) -> bool:
    """Return True if image has low standard deviation (blank untextured wall)."""
    if threshold <= 0:
        return False
    return float(gray.std()) < threshold


def is_rapid_turn(prev_gray: np.ndarray, curr_gray: np.ndarray, max_diff: float = 65.0) -> bool:
    """Return True if inter-frame pixel difference indicates a rapid camera whip-pan."""
    if prev_gray is None or max_diff <= 0:
        return False
    diff = float(np.mean(np.abs(curr_gray.astype(float) - prev_gray.astype(float))))
    return diff > max_diff


def extract_frames(
    input_path: str,
    output_dir: str = "output/frames",
    fps: float = 2.5,
    blur_threshold: float = 30.0,
    texture_threshold: float = 12.0,
    max_turn_diff: float = 65.0,
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
    print(f"[INFO] Extracting at {fps} FPS (blur_thresh={blur_threshold}, texture_thresh={texture_threshold}, turn_max={max_turn_diff})")

    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    # Interval in source frames between extractions
    frame_interval = max(1, int(round(video_fps / fps)))

    saved = 0
    skipped_blur = 0
    skipped_texture = 0
    skipped_turn = 0
    frame_idx = 0
    prev_saved_gray = None

    with tqdm(total=total_frames, desc="Processing frames", unit="fr") as pbar:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_idx % frame_interval == 0:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                if is_blurry(gray, blur_threshold):
                    skipped_blur += 1
                elif is_textureless(gray, texture_threshold):
                    skipped_texture += 1
                elif is_rapid_turn(prev_saved_gray, gray, max_turn_diff):
                    skipped_turn += 1
                else:
                    filename = out_path / f"frame_{saved:06d}.jpg"
                    cv2.imwrite(str(filename), frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
                    prev_saved_gray = gray
                    saved += 1

            frame_idx += 1
            pbar.update(1)

    cap.release()

    print(f"\n[DONE] Saved {saved} frames -> {out_path}")
    print(f"       Skipped: {skipped_blur} blurry, {skipped_texture} textureless, {skipped_turn} rapid-turn")
    if saved < 15:
        print("[WARN] Very few frames passed strict filters. Running fallback extraction at 2.5 FPS...")
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
        "--fps", type=float, default=2.5, help="Target frames per second to extract (default: 2.5)"
    )
    parser.add_argument(
        "--blur",
        type=float,
        default=30.0,
        help="Laplacian variance threshold for blur detection (default: 30.0)",
    )
    parser.add_argument(
        "--texture",
        type=float,
        default=12.0,
        help="Luminance standard deviation threshold for blank wall rejection (default: 12.0)",
    )
    parser.add_argument(
        "--turn-max",
        type=float,
        default=65.0,
        help="Maximum inter-frame difference for rapid turn/shake rejection (default: 65.0)",
    )
    args = parser.parse_args()
    extract_frames(args.input, args.output, args.fps, args.blur, args.texture, args.turn_max)


if __name__ == "__main__":
    main()
