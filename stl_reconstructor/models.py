from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import numpy as np


class PrimitiveType(str, Enum):
    PLANE = "plane"
    CYLINDER = "cylinder"
    SPHERE = "sphere"
    CONE = "cone"
    TORUS = "torus"
    HELIX = "helix"
    FREEFORM = "freeform"


@dataclass
class PrimitiveFeature:
    feature_id: int
    primitive: PrimitiveType
    params: dict[str, Any]
    inlier_indices: np.ndarray
    rmse_mm: float
    confidence: float
    boundary_vertex_indices: np.ndarray = field(default_factory=lambda: np.empty(0, dtype=np.int64))
    adjacency: set[int] = field(default_factory=set)

    @staticmethod
    def _jsonable(value):
        if isinstance(value, np.ndarray):
            return value.tolist()
        if isinstance(value, (np.floating, np.float32, np.float64)):
            return float(value)
        if isinstance(value, (np.integer, np.int32, np.int64)):
            return int(value)
        if isinstance(value, dict):
            return {str(k): PrimitiveFeature._jsonable(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [PrimitiveFeature._jsonable(v) for v in value]
        return value

    def to_dict(self) -> dict[str, Any]:
        return {
            "feature_id": self.feature_id,
            "primitive": self.primitive.value,
            "params": self._jsonable(self.params),
            "inlier_count": int(self.inlier_indices.size),
            "rmse_mm": float(self.rmse_mm),
            "confidence": float(self.confidence),
            "adjacency": sorted(int(v) for v in self.adjacency),
        }


@dataclass
class ProcessedMesh:
    mesh: Any
    vertices: np.ndarray
    vertex_normals: np.ndarray
    sampled_points: np.ndarray
    sampled_normals: np.ndarray
    sampled_to_vertex_map: np.ndarray
    metadata: dict[str, Any]


@dataclass
class BRepBuildInfo:
    solid: Any | None
    shell: Any | None
    faces: list[Any]
    valid: bool
    watertight: bool
    self_intersection_free: bool
    diagnostics: list[str] = field(default_factory=list)


@dataclass
class ReconstructionResult:
    input_stl: Path
    output_step: Path
    features: list[PrimitiveFeature]
    processed_mesh: ProcessedMesh
    brep: BRepBuildInfo
    elapsed_sec: float
    quality_mode: str
    stats: dict[str, Any]
