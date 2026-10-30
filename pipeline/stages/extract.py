"""
pipeline/stages/extract.py
──────────────────────────
Stage 1: Ingestion & Frame Extraction.
Accepts either an input video (.mp4/.mov) or a folder of existing images.
"""

from pathlib import Path
import shutil
import sys
from typing import Any, Dict
import cv2
from tqdm import tqdm
from .base import BaseStage
from ..config import PipelineConfig


def is_blurry(frame, threshold: float) -> bool:
    if threshold <= 0:
        return False
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return cv2.Laplacian(gray, cv2.CV_64F).var() < threshold


class ExtractStage(BaseStage):
    def __init__(self):
        super().__init__(
            name="extract",
            description="Extract and filter keyframes from video or link input image directory",
        )

    def is_cached(self, out_dir: Path, config: PipelineConfig) -> bool:
        frames_dir = out_dir / "frames"
        if not frames_dir.exists():
            return False
        return len(list(frames_dir.glob("*.jpg"))) > 0

    def execute(
        self,
        input_path: Path,
        out_dir: Path,
        config: PipelineConfig,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        frames_dir = out_dir / "frames"
        frames_dir.mkdir(parents=True, exist_ok=True)

        if input_path.is_dir():
            print(f"[INFO] Input is a directory. Linking/copying images from: {input_path}")
            valid_exts = {".jpg", ".jpeg", ".png", ".webp"}
            found = sorted([p for p in input_path.iterdir() if p.suffix.lower() in valid_exts])
            if not found:
                raise RuntimeError(f"No valid images found in directory: {input_path}")
            for idx, p in enumerate(found):
                dst = frames_dir / f"frame_{idx:06d}.jpg"
                if not dst.exists():
                    shutil.copy2(str(p), str(dst))
            print(f"[OK] Indexed {len(found)} frames into {frames_dir}")
            context["frames_dir"] = frames_dir
            context["frame_count"] = len(found)
            return context

        # Input is a video
        cap = cv2.VideoCapture(str(input_path))
        if not cap.isOpened():
            raise RuntimeError(f"Cannot open video file: {input_path}")

        video_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
        target_fps = config.frame_sampling.fps
        blur_thresh = config.frame_sampling.blur_threshold
        quality = config.frame_sampling.quality
        frame_interval = max(1, int(round(video_fps / target_fps)))

        print(f"[INFO] Video: {input_path}")
        print(f"[INFO] Native FPS: {video_fps:.2f}, Total frames: {total_frames}")
        print(f"[INFO] Sampling target: {target_fps} FPS (1 frame every {frame_interval} source frames)")

        saved = 0
        frame_idx = 0
        with tqdm(total=total_frames, desc="Extracting frames", unit="fr") as pbar:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                if frame_idx % frame_interval == 0:
                    if not is_blurry(frame, blur_thresh):
                        filename = frames_dir / f"frame_{saved:06d}.jpg"
                        cv2.imwrite(str(filename), frame, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
                        saved += 1
                frame_idx += 1
                pbar.update(1)
        cap.release()

        # Fallback if blur threshold was too aggressive
        if saved == 0:
            print("[WARN] No frames passed blur threshold. Re-extracting without blur filter...")
            cap = cv2.VideoCapture(str(input_path))
            frame_idx = 0
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                if frame_idx % frame_interval == 0:
                    filename = frames_dir / f"frame_{saved:06d}.jpg"
                    cv2.imwrite(str(filename), frame, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
                    saved += 1
                frame_idx += 1
            cap.release()

        print(f"[OK] Extracted {saved} frames into {frames_dir}")
        context["frames_dir"] = frames_dir
        context["frame_count"] = saved
        return context
