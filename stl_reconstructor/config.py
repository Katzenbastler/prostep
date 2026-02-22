from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class QualityMode(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    ULTRA = "ultra"


@dataclass(frozen=True)
class QualityProfile:
    voxel_size_mm: float
    smoothing_iterations: int
    smoothing_sharp_angle_deg: float
    max_ransac_iterations: int
    inlier_threshold_mm: float
    min_inlier_ratio: float
    primitive_types: tuple[str, ...]
    multi_stage_ransac: bool
    region_growing_refine: bool
    thread_detection: bool
    boolean_feature_detection: bool
    continuity_analysis: bool


QUALITY_PROFILES: dict[QualityMode, QualityProfile] = {
    QualityMode.LOW: QualityProfile(
        voxel_size_mm=0.75,
        smoothing_iterations=1,
        smoothing_sharp_angle_deg=40.0,
        max_ransac_iterations=180,
        inlier_threshold_mm=0.60,
        min_inlier_ratio=0.06,
        primitive_types=("plane", "cylinder"),
        multi_stage_ransac=False,
        region_growing_refine=False,
        thread_detection=False,
        boolean_feature_detection=False,
        continuity_analysis=False,
    ),
    QualityMode.MEDIUM: QualityProfile(
        voxel_size_mm=0.35,
        smoothing_iterations=2,
        smoothing_sharp_angle_deg=35.0,
        max_ransac_iterations=380,
        inlier_threshold_mm=0.30,
        min_inlier_ratio=0.05,
        primitive_types=("plane", "cylinder", "sphere"),
        multi_stage_ransac=False,
        region_growing_refine=True,
        thread_detection=False,
        boolean_feature_detection=False,
        continuity_analysis=False,
    ),
    QualityMode.HIGH: QualityProfile(
        voxel_size_mm=0.15,
        smoothing_iterations=3,
        smoothing_sharp_angle_deg=30.0,
        max_ransac_iterations=850,
        inlier_threshold_mm=0.12,
        min_inlier_ratio=0.03,
        primitive_types=("plane", "cylinder", "sphere", "cone", "torus"),
        multi_stage_ransac=True,
        region_growing_refine=True,
        thread_detection=False,
        boolean_feature_detection=True,
        continuity_analysis=True,
    ),
    QualityMode.ULTRA: QualityProfile(
        voxel_size_mm=0.05,
        smoothing_iterations=4,
        smoothing_sharp_angle_deg=28.0,
        max_ransac_iterations=1800,
        inlier_threshold_mm=0.01,
        min_inlier_ratio=0.02,
        primitive_types=("plane", "cylinder", "sphere", "cone", "torus", "helix"),
        multi_stage_ransac=True,
        region_growing_refine=True,
        thread_detection=True,
        boolean_feature_detection=True,
        continuity_analysis=True,
    ),
}


@dataclass
class ReconstructionConfig:
    quality_mode: QualityMode = QualityMode.MEDIUM
    enable_smoothing: bool = True
    prefer_analytic_surfaces: bool = True
    export_tolerance_mm: float = 0.01
    export_unit: str = "MM"
    random_seed: int = 1337
    ransac_workers: int = 0
    max_features: int = 120
    min_cluster_vertices: int = 60
    verbose: bool = False
    profile_overrides: dict[str, float | int | bool | tuple[str, ...]] = field(default_factory=dict)

    @property
    def profile(self) -> QualityProfile:
        base = QUALITY_PROFILES[self.quality_mode]
        if not self.profile_overrides:
            return base
        data = {**base.__dict__, **self.profile_overrides}
        return QualityProfile(**data)
