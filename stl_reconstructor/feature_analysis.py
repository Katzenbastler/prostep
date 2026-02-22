from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy.spatial import cKDTree

from .fitting import normalize
from .models import PrimitiveFeature, PrimitiveType, ProcessedMesh
from .segmentation import SegmentationOutput


def _dominant_axes(features: list[PrimitiveFeature], eps_deg: float = 7.0) -> list[np.ndarray]:
    axes = []
    for f in features:
        if f.primitive in (PrimitiveType.CYLINDER, PrimitiveType.CONE, PrimitiveType.HELIX, PrimitiveType.TORUS):
            axis = f.params.get("axis_dir")
            if axis is not None:
                axes.append(normalize(np.asarray(axis, dtype=np.float64)))
    if not axes:
        return []
    merged: list[np.ndarray] = []
    for ax in axes:
        found = False
        for i, m in enumerate(merged):
            if abs(float(np.dot(ax, m))) >= math.cos(math.radians(eps_deg)):
                merged[i] = normalize(m + np.sign(np.dot(ax, m)) * ax)
                found = True
                break
        if not found:
            merged.append(ax.copy())
    return merged


def detect_boolean_like_features(features: list[PrimitiveFeature], seg: SegmentationOutput) -> dict[str, int]:
    through_holes = 0
    blind_holes = 0
    pockets = 0
    ribs = 0

    for f in features:
        if f.primitive == PrimitiveType.CYLINDER:
            neigh = len(f.adjacency)
            if neigh >= 3 and f.params.get("radius", 0.0) < 10.0:
                through_holes += 1
            elif neigh == 2:
                blind_holes += 1
        if f.primitive == PrimitiveType.PLANE:
            neigh = len(f.adjacency)
            if neigh >= 4:
                pockets += 1
            elif neigh == 2:
                ribs += 1

    return {
        "through_holes": through_holes,
        "blind_holes": blind_holes,
        "pockets": pockets,
        "ribs": ribs,
    }


def detect_symmetry(processed: ProcessedMesh, sample_count: int = 8000) -> dict[str, bool]:
    points = processed.vertices
    if points.shape[0] < 40:
        return {"mirror_xy": False, "mirror_yz": False, "mirror_xz": False}
    if points.shape[0] > sample_count:
        rng = np.random.default_rng(1337)
        idx = rng.choice(points.shape[0], sample_count, replace=False)
        points = points[idx]
    tree = cKDTree(points)

    def check_axis(mirror: np.ndarray) -> bool:
        mirrored = points.copy()
        mirrored[:, mirror.astype(bool)] *= -1.0
        dist, _ = tree.query(mirrored, k=1)
        return float(np.median(dist)) < 0.2

    return {
        "mirror_xy": check_axis(np.array([0, 0, 1])),
        "mirror_yz": check_axis(np.array([1, 0, 0])),
        "mirror_xz": check_axis(np.array([0, 1, 0])),
    }


def detect_rotational_bodies(features: list[PrimitiveFeature]) -> bool:
    axes = _dominant_axes(features)
    return len(axes) <= 2 and len(axes) > 0 and sum(1 for f in features if f.primitive in {PrimitiveType.CYLINDER, PrimitiveType.CONE, PrimitiveType.SPHERE}) >= 3

