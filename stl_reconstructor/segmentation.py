from __future__ import annotations

import math
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Callable

import numpy as np
from scipy.spatial import cKDTree

from .config import ReconstructionConfig
from .fitting import PRIMITIVE_KERNELS
from .models import PrimitiveFeature, PrimitiveType, ProcessedMesh

ProgressCallback = Callable[[float, str], None]


@dataclass
class SegmentationOutput:
    features: list[PrimitiveFeature]
    sampled_labels: np.ndarray
    vertex_labels: np.ndarray
    face_labels: np.ndarray


class RansacSegmenter:
    def __init__(self, config: ReconstructionConfig, progress: ProgressCallback | None = None) -> None:
        self.config = config
        self.progress = progress
        self.rng = np.random.default_rng(config.random_seed)

    def _emit(self, fraction: float, message: str) -> None:
        if self.progress:
            self.progress(float(max(0.0, min(1.0, fraction))), message)

    def _evaluate_type(
        self,
        primitive_name: str,
        points: np.ndarray,
        threshold: float,
        iterations: int,
        min_inliers: int,
    ) -> tuple[str, dict[str, np.ndarray | dict | float] | None]:
        kernel = PRIMITIVE_KERNELS[primitive_name]
        n = points.shape[0]
        if n < max(kernel.min_samples, min_inliers):
            return primitive_name, None

        best_model = None
        best_inliers = None
        best_rmse = float("inf")
        best_count = 0

        for _ in range(iterations):
            sample_idx = self.rng.choice(n, size=kernel.min_samples, replace=False)
            model = kernel.fit_fn(points[sample_idx])
            if model is None:
                continue
            dist = kernel.dist_fn(points, model)
            inliers = dist <= threshold
            count = int(np.count_nonzero(inliers))
            if count < min_inliers:
                continue
            rmse = float(np.sqrt(np.mean(dist[inliers] ** 2)))
            if count > best_count or (count == best_count and rmse < best_rmse):
                best_model = model
                best_inliers = inliers
                best_rmse = rmse
                best_count = count

        if best_model is None or best_inliers is None:
            return primitive_name, None

        refit = kernel.fit_fn(points[best_inliers])
        if refit is not None:
            dist = kernel.dist_fn(points, refit)
            inliers = dist <= threshold
            count = int(np.count_nonzero(inliers))
            if count >= min_inliers:
                best_model = refit
                best_inliers = inliers
                best_rmse = float(np.sqrt(np.mean(dist[inliers] ** 2)))
                best_count = count

        return primitive_name, {
            "model": best_model,
            "inliers": best_inliers,
            "rmse": best_rmse,
            "count": best_count,
        }

    def _evaluate_type_multistage(
        self,
        primitive_name: str,
        points: np.ndarray,
        threshold: float,
        iterations: int,
        min_inliers: int,
    ) -> tuple[str, dict[str, np.ndarray | dict | float] | None]:
        coarse_threshold = threshold * 2.0
        coarse_iterations = max(40, iterations // 3)
        _, coarse = self._evaluate_type(
            primitive_name=primitive_name,
            points=points,
            threshold=coarse_threshold,
            iterations=coarse_iterations,
            min_inliers=min_inliers,
        )
        if coarse is None:
            return primitive_name, None

        coarse_inliers = coarse["inliers"]
        assert isinstance(coarse_inliers, np.ndarray)
        refined_points = points[coarse_inliers]
        if refined_points.shape[0] < min_inliers:
            return primitive_name, None

        _, fine = self._evaluate_type(
            primitive_name=primitive_name,
            points=refined_points,
            threshold=threshold,
            iterations=max(60, iterations // 2),
            min_inliers=max(12, int(min_inliers * 0.65)),
        )
        if fine is None:
            return primitive_name, coarse

        fine_model = fine["model"]
        assert fine_model is not None
        dist_fn = PRIMITIVE_KERNELS[primitive_name].dist_fn
        final_dist = dist_fn(points, fine_model)
        final_inliers = final_dist <= threshold
        count = int(np.count_nonzero(final_inliers))
        if count < min_inliers:
            return primitive_name, coarse
        rmse = float(np.sqrt(np.mean(final_dist[final_inliers] ** 2)))
        return primitive_name, {"model": fine_model, "inliers": final_inliers, "rmse": rmse, "count": count}

    @staticmethod
    def _primitive_from_name(name: str) -> PrimitiveType:
        return PrimitiveType(name)

    @staticmethod
    def _annotate_helix_model(model: dict, points: np.ndarray, normals: np.ndarray) -> dict:
        axis = np.asarray(model["axis_dir"], dtype=np.float64)
        axis = axis / max(np.linalg.norm(axis), 1e-12)
        origin = np.asarray(model["axis_point"], dtype=np.float64)
        q = points - origin
        axial = np.outer(q @ axis, axis)
        radial = q - axial
        radial_n = radial / np.maximum(np.linalg.norm(radial, axis=1, keepdims=True), 1e-9)
        normal_n = normals / np.maximum(np.linalg.norm(normals, axis=1, keepdims=True), 1e-9)
        orient = float(np.median(np.einsum("ij,ij->i", radial_n, normal_n)))
        model["thread_kind"] = "external" if orient >= 0.0 else "internal"
        pitch = float(model["pitch"])
        major_d = float(model["major_diameter"])
        model["lead_angle_deg"] = float(np.degrees(np.arctan2(pitch, math.pi * max(major_d, 1e-9))))
        model["iso_metric_guess"] = RansacSegmenter._guess_metric_thread(major_d, pitch)
        return model

    @staticmethod
    def _guess_metric_thread(major_diameter_mm: float, pitch_mm: float) -> str | None:
        iso_table = [
            (3.0, 0.5),
            (4.0, 0.7),
            (5.0, 0.8),
            (6.0, 1.0),
            (8.0, 1.25),
            (10.0, 1.5),
            (12.0, 1.75),
            (16.0, 2.0),
            (20.0, 2.5),
            (24.0, 3.0),
            (30.0, 3.5),
            (36.0, 4.0),
        ]
        best = None
        best_err = float("inf")
        for major, pitch in iso_table:
            err = abs(major - major_diameter_mm) + 1.5 * abs(pitch - pitch_mm)
            if err < best_err:
                best_err = err
                best = f"M{major:g}x{pitch:g}"
        return best if best_err < 1.0 else None

    def _fit_remaining(
        self,
        points: np.ndarray,
        primitive_names: tuple[str, ...],
        threshold: float,
        iterations: int,
        min_inliers: int,
        use_multistage: bool,
    ) -> dict[str, dict[str, np.ndarray | dict | float]]:
        results: dict[str, dict[str, np.ndarray | dict | float]] = {}

        workers = self.config.ransac_workers if self.config.ransac_workers > 0 else min(len(primitive_names), 8)
        evaluator = self._evaluate_type_multistage if use_multistage else self._evaluate_type
        if workers <= 1 or len(primitive_names) == 1:
            for p in primitive_names:
                _, out = evaluator(
                    primitive_name=p,
                    points=points,
                    threshold=threshold,
                    iterations=iterations,
                    min_inliers=min_inliers,
                )
                if out is not None:
                    results[p] = out
            return results

        with ThreadPoolExecutor(max_workers=workers) as ex:
            futures = [
                ex.submit(
                    evaluator,
                    p,
                    points,
                    threshold,
                    iterations,
                    min_inliers,
                )
                for p in primitive_names
            ]
            for fut in futures:
                primitive_name, out = fut.result()
                if out is not None:
                    results[primitive_name] = out
        return results

    def _region_growing_refine(
        self,
        points: np.ndarray,
        labels: np.ndarray,
        features: list[PrimitiveFeature],
    ) -> np.ndarray:
        if points.shape[0] < 20 or len(features) < 2:
            return labels

        tree = cKDTree(points)
        current = labels.copy()
        feature_map = {f.feature_id: f for f in features}

        def residual_to_feature(fid: int, pts: np.ndarray) -> np.ndarray:
            f = feature_map[fid]
            if f.primitive == PrimitiveType.FREEFORM:
                return np.full(pts.shape[0], np.inf, dtype=np.float64)
            kernel = PRIMITIVE_KERNELS[f.primitive.value]
            return kernel.dist_fn(pts, f.params)

        for _ in range(3):
            unknown = np.where(current < 0)[0]
            if unknown.size == 0:
                break
            _, nn = tree.query(points[unknown], k=min(16, points.shape[0]))
            for local_idx, pidx in enumerate(unknown):
                neigh = nn[local_idx]
                neigh = neigh if np.ndim(neigh) > 0 else np.array([neigh], dtype=np.int64)
                neigh_labels = current[np.asarray(neigh, dtype=np.int64)]
                neigh_labels = neigh_labels[neigh_labels >= 0]
                if neigh_labels.size == 0:
                    continue
                values, counts = np.unique(neigh_labels, return_counts=True)
                candidate = int(values[np.argmax(counts)])
                res = residual_to_feature(candidate, points[pidx : pidx + 1])[0]
                if np.isfinite(res):
                    current[pidx] = candidate
        return current

    def _merge_similar(self, features: list[PrimitiveFeature], threshold: float) -> list[PrimitiveFeature]:
        merged: list[PrimitiveFeature] = []
        consumed: set[int] = set()

        def nearly_parallel(a: np.ndarray, b: np.ndarray, deg: float = 5.0) -> bool:
            dot = abs(float(np.dot(a / np.linalg.norm(a), b / np.linalg.norm(b))))
            return dot >= math.cos(math.radians(deg))

        for i, f in enumerate(features):
            if i in consumed or f.primitive == PrimitiveType.FREEFORM:
                continue
            group = [f]
            for j in range(i + 1, len(features)):
                g = features[j]
                if j in consumed or g.primitive != f.primitive:
                    continue
                if f.primitive == PrimitiveType.PLANE:
                    if nearly_parallel(f.params["normal"], g.params["normal"]) and abs(f.params["d"] - g.params["d"]) < threshold:
                        group.append(g)
                        consumed.add(j)
                elif f.primitive == PrimitiveType.CYLINDER:
                    if nearly_parallel(f.params["axis_dir"], g.params["axis_dir"]) and abs(f.params["radius"] - g.params["radius"]) < threshold * 2.0:
                        group.append(g)
                        consumed.add(j)
                elif f.primitive == PrimitiveType.SPHERE:
                    if (
                        np.linalg.norm(f.params["center"] - g.params["center"]) < threshold * 2.0
                        and abs(f.params["radius"] - g.params["radius"]) < threshold * 2.0
                    ):
                        group.append(g)
                        consumed.add(j)

            if len(group) == 1:
                merged.append(f)
                continue

            all_inliers = np.unique(np.concatenate([x.inlier_indices for x in group]))
            rmse = float(np.mean([x.rmse_mm for x in group]))
            confidence = float(np.mean([x.confidence for x in group]))
            base = group[0]
            merged.append(
                PrimitiveFeature(
                    feature_id=base.feature_id,
                    primitive=base.primitive,
                    params=base.params,
                    inlier_indices=all_inliers,
                    rmse_mm=rmse,
                    confidence=confidence,
                )
            )
        freeforms = [f for f in features if f.primitive == PrimitiveType.FREEFORM]
        merged.extend(freeforms)
        return merged

    def run(self, processed: ProcessedMesh) -> SegmentationOutput:
        profile = self.config.profile
        points = processed.sampled_points
        total_n = points.shape[0]
        self._emit(0.52, "RANSAC feature segmentation")

        remaining = np.ones(total_n, dtype=bool)
        features: list[PrimitiveFeature] = []
        sampled_labels = np.full(total_n, -1, dtype=np.int64)
        feature_id = 0
        primitive_names = tuple(profile.primitive_types)
        min_inliers = max(
            self.config.min_cluster_vertices,
            int(max(profile.min_inlier_ratio * total_n, 3)),
        )

        while feature_id < self.config.max_features:
            rem_idx = np.where(remaining)[0]
            if rem_idx.size < min_inliers:
                break
            rem_points = points[rem_idx]

            candidates = self._fit_remaining(
                points=rem_points,
                primitive_names=primitive_names,
                threshold=profile.inlier_threshold_mm,
                iterations=profile.max_ransac_iterations,
                min_inliers=min_inliers,
                use_multistage=profile.multi_stage_ransac,
            )
            if not candidates:
                break

            best_name = None
            best_payload = None
            best_score = -np.inf
            for name, payload in candidates.items():
                count = float(payload["count"])
                rmse = float(payload["rmse"])
                score = count / (rmse + 1e-6)
                if profile.thread_detection and name == "helix":
                    score *= 1.2
                if score > best_score:
                    best_name = name
                    best_payload = payload
                    best_score = score

            if best_name is None or best_payload is None:
                break

            inliers_local = best_payload["inliers"]
            assert isinstance(inliers_local, np.ndarray)
            inliers_global = rem_idx[inliers_local]
            if inliers_global.size < min_inliers:
                break

            rmse = float(best_payload["rmse"])
            ratio = float(inliers_global.size / max(1, rem_idx.size))
            confidence = float(np.clip(1.0 - rmse / (profile.inlier_threshold_mm + 1e-9), 0.0, 1.0) * ratio)

            primitive = self._primitive_from_name(best_name)
            model = best_payload["model"]
            assert isinstance(model, dict)
            if primitive == PrimitiveType.HELIX:
                normals = processed.sampled_normals[inliers_global]
                model = self._annotate_helix_model(model, points[inliers_global], normals)

            features.append(
                PrimitiveFeature(
                    feature_id=feature_id,
                    primitive=primitive,
                    params=model,
                    inlier_indices=inliers_global.astype(np.int64),
                    rmse_mm=rmse,
                    confidence=confidence,
                )
            )
            sampled_labels[inliers_global] = feature_id
            remaining[inliers_global] = False
            feature_id += 1

            progressed = 0.52 + min(0.22, 0.22 * (1.0 - np.count_nonzero(remaining) / max(1, total_n)))
            self._emit(progressed, f"Feature {feature_id}: {primitive.value}")

        if np.any(remaining):
            leftover = np.where(remaining)[0]
            features.append(
                PrimitiveFeature(
                    feature_id=feature_id,
                    primitive=PrimitiveType.FREEFORM,
                    params={"method": "bspline_fallback"},
                    inlier_indices=leftover.astype(np.int64),
                    rmse_mm=0.0,
                    confidence=0.0,
                )
            )
            sampled_labels[leftover] = feature_id

        if profile.region_growing_refine:
            sampled_labels = self._region_growing_refine(points=points, labels=sampled_labels, features=features)

        # Build face and adjacency labels on original mesh vertices.
        self._emit(0.75, "Build feature graph and boundaries")
        tree = cKDTree(points)
        _, nearest = tree.query(processed.vertices, k=1)
        vertex_labels = sampled_labels[np.asarray(nearest, dtype=np.int64)]

        faces = processed.mesh.faces
        face_votes = vertex_labels[faces]
        face_labels = np.array(
            [np.bincount(v[v >= 0]).argmax() if np.any(v >= 0) else -1 for v in face_votes],
            dtype=np.int64,
        )

        # Feature boundary vertices.
        edges = np.asarray(processed.mesh.edges_unique, dtype=np.int64)
        edge_labels_a = vertex_labels[edges[:, 0]]
        edge_labels_b = vertex_labels[edges[:, 1]]
        boundary_edges = edges[edge_labels_a != edge_labels_b]
        for feature in features:
            mask = (vertex_labels[boundary_edges[:, 0]] == feature.feature_id) | (
                vertex_labels[boundary_edges[:, 1]] == feature.feature_id
            )
            b = np.unique(boundary_edges[mask])
            feature.boundary_vertex_indices = b.astype(np.int64)

        # Feature adjacency from face adjacency.
        if len(processed.mesh.face_adjacency) > 0:
            for a, b in processed.mesh.face_adjacency:
                la = int(face_labels[a])
                lb = int(face_labels[b])
                if la >= 0 and lb >= 0 and la != lb:
                    if la < len(features):
                        features[la].adjacency.add(lb)
                    if lb < len(features):
                        features[lb].adjacency.add(la)

        features = self._merge_similar(features, threshold=profile.inlier_threshold_mm)
        return SegmentationOutput(
            features=features,
            sampled_labels=sampled_labels,
            vertex_labels=vertex_labels,
            face_labels=face_labels,
        )
