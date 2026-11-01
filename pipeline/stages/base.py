"""
pipeline/stages/base.py
───────────────────────
Abstract base class for all pipeline execution stages.
"""

from abc import ABC, abstractmethod
import json
from pathlib import Path
import time
from typing import Any, Dict
from ..config import PipelineConfig


class BaseStage(ABC):
    """Abstract base class for a modular pipeline stage."""

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description

    @abstractmethod
    def is_cached(self, out_dir: Path, config: PipelineConfig) -> bool:
        """Return True if stage outputs are already fully computed and valid."""
        pass

    @abstractmethod
    def execute(
        self,
        input_path: Path,
        out_dir: Path,
        config: PipelineConfig,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute stage logic. Returns updated context dictionary."""
        pass

    def run(
        self,
        input_path: Path,
        out_dir: Path,
        config: PipelineConfig,
        context: Dict[str, Any],
        force: bool = False,
    ) -> Dict[str, Any]:
        """Execute the stage with timing, logging, and caching checks."""
        print(f"\n{'='*60}")
        print(f"  Stage: {self.name.upper()} — {self.description}")
        print(f"{'='*60}")

        if not force and self.is_cached(out_dir, config):
            print(f"[CACHE] Skipping '{self.name}' — outputs already exist in {out_dir}.")
            return context

        t0 = time.perf_counter()
        result = self.execute(input_path, out_dir, config, context)
        elapsed = time.perf_counter() - t0

        print(f"[DONE] Stage '{self.name}' completed in {elapsed:.2f}s.")
        self._record_timing(out_dir, elapsed)
        return result

    def _record_timing(self, out_dir: Path, elapsed: float) -> None:
        timings_path = out_dir / "timings.json"
        timings = {}
        if timings_path.exists():
            try:
                timings = json.loads(timings_path.read_text(encoding="utf-8"))
            except Exception:
                timings = {}
        timings[self.name] = round(elapsed, 3)
        timings_path.write_text(json.dumps(timings, indent=2), encoding="utf-8")

