from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Callable

import numpy as np

from .brep_builder import BRepReconstructor
from .config import QualityMode, ReconstructionConfig
from .feature_analysis import detect_boolean_like_features, detect_rotational_bodies, detect_symmetry
from .models import ReconstructionResult
from .preprocess import MeshPreprocessor
from .segmentation import RansacSegmenter
from .step_export import export_step_ap242

ProgressCallback = Callable[[float, str], None]


def _continuity_stats(processed, segmentation) -> dict[str, int]:
    mesh = processed.mesh
    face_adj = np.asarray(mesh.face_adjacency, dtype=np.int64)
    if face_adj.size == 0:
        return {"g1_pairs": 0, "g2_pairs": 0}
    labels = segmentation.face_labels
    normals = np.asarray(mesh.face_normals, dtype=np.float64)
    g1 = 0
    g2 = 0
    for a, b in face_adj:
        la = int(labels[a])
        lb = int(labels[b])
        if la < 0 or lb < 0 or la == lb:
            continue
        dot = np.clip(float(np.dot(normals[a], normals[b])), -1.0, 1.0)
        angle_deg = float(np.degrees(np.arccos(dot)))
        if angle_deg < 4.0:
            g1 += 1
        if angle_deg < 1.0:
            g2 += 1
    return {"g1_pairs": g1, "g2_pairs": g2}


class ReconstructionPipeline:
    def __init__(self, config: ReconstructionConfig | None = None, progress: ProgressCallback | None = None) -> None:
        self.config = config or ReconstructionConfig()
        self.progress = progress

    def _emit(self, fraction: float, message: str) -> None:
        if self.progress:
            self.progress(float(max(0.0, min(1.0, fraction))), message)

    def _make_subprogress(self, start: float, end: float) -> ProgressCallback:
        span = max(1e-9, end - start)

        def callback(p: float, message: str) -> None:
            self._emit(start + span * max(0.0, min(1.0, p)), message)

        return callback

    def run(self, input_stl: str | Path, output_step: str | Path | None = None) -> ReconstructionResult:
        t0 = time.perf_counter()
        input_stl = Path(input_stl).resolve()
        if output_step is None:
            output_step = input_stl.with_name(f"{input_stl.stem}_reconstructed.step")
        output_step = Path(output_step).resolve()

        self._emit(0.0, "Start reconstruction pipeline")
        processed = MeshPreprocessor(self.config, progress=self._make_subprogress(0.0, 0.52)).run(input_stl)
        segmentation = RansacSegmenter(self.config, progress=self._make_subprogress(0.52, 0.78)).run(processed)
        brep = BRepReconstructor(
            tolerance_mm=self.config.export_tolerance_mm,
            prefer_analytic_surfaces=self.config.prefer_analytic_surfaces,
            progress=self._make_subprogress(0.78, 0.97),
        ).build(processed, segmentation)

        self._emit(0.97, "Export STEP AP242")
        export_step_ap242(
            brep=brep,
            out_path=output_step,
            unit=self.config.export_unit,
            tolerance_mm=self.config.export_tolerance_mm,
        )
        self._emit(1.0, "Finished")

        features = segmentation.features
        primitive_counts = Counter(f.primitive.value for f in features)
        extra = {}
        if self.config.profile.boolean_feature_detection:
            extra["boolean_like"] = detect_boolean_like_features(features, segmentation)
        if self.config.profile.continuity_analysis:
            extra["continuity"] = _continuity_stats(processed, segmentation)
        # Keep low/medium mode faster by skipping expensive global analyses.
        if self.config.quality_mode in (QualityMode.HIGH, QualityMode.ULTRA):
            extra["symmetry"] = detect_symmetry(processed)
            extra["rotational_body"] = detect_rotational_bodies(features)
        else:
            extra["symmetry"] = []
            extra["rotational_body"] = []

        elapsed = time.perf_counter() - t0
        stats = {
            "elapsed_sec": elapsed,
            "mesh": processed.metadata,
            "primitive_counts": dict(primitive_counts),
            "brep_valid": brep.valid,
            "brep_watertight": brep.watertight,
            "self_intersection_free": brep.self_intersection_free,
            "extra_analysis": extra,
        }

        json_report = output_step.with_suffix(".json")
        report = {
            "input_stl": input_stl.name,
            "output_step": output_step.name,
            "paths_redacted": True,
            "quality_mode": self.config.quality_mode.value,
            "features": [f.to_dict() for f in features],
            "stats": stats,
            "diagnostics": brep.diagnostics,
        }
        json_report.write_text(json.dumps(report, indent=2), encoding="utf-8")

        return ReconstructionResult(
            input_stl=input_stl,
            output_step=output_step,
            features=features,
            processed_mesh=processed,
            brep=brep,
            elapsed_sec=elapsed,
            quality_mode=self.config.quality_mode.value,
            stats=stats,
        )
