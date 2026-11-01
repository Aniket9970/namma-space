"""
pipeline/config.py
──────────────────
Configuration loader and validator for the Namma Space pipeline.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml


@dataclass
class GeneralConfig:
    units: str = "m"
    coordinate_system: str = "Y-up"
    target_floor_y: float = 0.0
    eye_height: float = 1.65
    scale_method: str = "colmap_relative"
    reference_dimension_m: float = 2.0


@dataclass
class FrameSamplingConfig:
    fps: float = 2.5
    blur_threshold: float = 15.0
    quality: int = 95
    max_dimension: int = 1920
    rotation: int = 0  # 0, 90, 180, 270 degrees clockwise


@dataclass
class ColmapConfig:
    camera_model: str = "SIMPLE_RADIAL"
    single_camera: bool = True
    feature_max_size: int = 1600
    max_features: int = 8192
    num_threads: int = 12
    matching_overlap: int = 15
    use_gpu: bool = False


@dataclass
class VggtConfig:
    window_size: int = 16
    window_overlap: int = 4
    device: str = "cuda"


@dataclass
class PoseBackendConfig:
    backend: str = "auto"  # "colmap", "vggt", "auto"
    colmap: ColmapConfig = field(default_factory=ColmapConfig)
    vggt: VggtConfig = field(default_factory=VggtConfig)


@dataclass
class FloorAlignmentConfig:
    ransac_threshold_m: float = 0.05
    min_inlier_ratio: float = 0.15
    search_height_fraction: float = 0.4
    max_iterations: int = 2000


@dataclass
class PanoramasConfig:
    node_spacing_m: float = 2.5
    min_node_spacing_m: float = 1.5
    equirect_width: int = 4096
    equirect_height: int = 2048
    lod_width: int = 1024
    lod_height: int = 512
    blending: str = "multiband"
    frame_window: int = 5


@dataclass
class DepthProxyConfig:
    backend: str = "depth_anything_v2"
    device: str = "cuda"
    tsdf_voxel_length_m: float = 0.04
    tsdf_sdf_trunc_m: float = 0.16
    max_triangles: int = 50000
    target_max_size_mb: float = 5.0
    align_to_sfm_points: bool = True


@dataclass
class NavigationConfig:
    grid_resolution_m: float = 0.05
    obstacle_slice_min_y: float = 0.20
    obstacle_slice_max_y: float = 1.80
    agent_radius_m: float = 0.30
    morphological_kernel: int = 3
    min_cluster_cells: int = 8
    planner: str = "astar"


@dataclass
class PhotorealSplatConfig:
    enabled: bool = True
    iterations: int = 10000
    data_device: str = "cpu"
    resolution_scale: int = -1
    densify_grad_threshold: float = 0.0002
    sh_degree: int = 3


@dataclass
class PipelineConfig:
    general: GeneralConfig = field(default_factory=GeneralConfig)
    frame_sampling: FrameSamplingConfig = field(default_factory=FrameSamplingConfig)
    pose_backend: PoseBackendConfig = field(default_factory=PoseBackendConfig)
    floor_alignment: FloorAlignmentConfig = field(default_factory=FloorAlignmentConfig)
    panoramas: PanoramasConfig = field(default_factory=PanoramasConfig)
    depth_proxy: DepthProxyConfig = field(default_factory=DepthProxyConfig)
    navigation: NavigationConfig = field(default_factory=NavigationConfig)
    photoreal_splat: PhotorealSplatConfig = field(default_factory=PhotorealSplatConfig)
    raw_dict: Dict[str, Any] = field(default_factory=dict)


def load_config(config_path: Optional[Path | str] = None) -> PipelineConfig:
    """Load configuration from YAML file or return defaults."""
    if config_path is None:
        candidates = [
            Path("config.yaml"),
            Path(__file__).resolve().parent.parent / "config.yaml",
        ]
        for c in candidates:
            if c.exists():
                config_path = c
                break

    raw: Dict[str, Any] = {}
    if config_path and Path(config_path).exists():
        with open(config_path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}

    cfg = PipelineConfig(
        general=GeneralConfig(**raw.get("general", {})),
        frame_sampling=FrameSamplingConfig(**raw.get("frame_sampling", {})),
        pose_backend=PoseBackendConfig(
            backend=raw.get("pose_backend", {}).get("backend", "auto"),
            colmap=ColmapConfig(**raw.get("pose_backend", {}).get("colmap", {})),
            vggt=VggtConfig(**raw.get("pose_backend", {}).get("vggt", {})),
        ),
        floor_alignment=FloorAlignmentConfig(**raw.get("floor_alignment", {})),
        panoramas=PanoramasConfig(**raw.get("panoramas", {})),
        depth_proxy=DepthProxyConfig(**raw.get("depth_proxy", {})),
        navigation=NavigationConfig(**raw.get("navigation", {})),
        photoreal_splat=PhotorealSplatConfig(**raw.get("photoreal_splat", {})),
        raw_dict=raw,
    )
    return cfg

