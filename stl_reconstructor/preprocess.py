from __future__ import annotations

from pathlib import Path
from typing import Callable

import numpy as np
import trimesh

from .config import ReconstructionConfig
from .models import ProcessedMesh

ProgressCallback = Callable[[float, str], None]


class MeshPreprocessor:
    def __init__(self, config: ReconstructionConfig, progress: ProgressCallback | None = None) -> None:
        self.config = config
        self.progress = progress

    def _emit(self, fraction: float, message: str) -> None:
        if self.progress:
            self.progress(float(max(0.0, min(1.0, fraction))), message)

    @staticmethod
    def _count_non_manifold_edges(mesh: trimesh.Trimesh) -> int:
        edges = np.sort(mesh.edges, axis=1)
        _, counts = np.unique(edges, axis=0, return_counts=True)
        return int(np.count_nonzero(counts > 2))

    @staticmethod
    def _feature_aware_smooth(
        mesh: trimesh.Trimesh,
        iterations: int,
        sharp_angle_deg: float,
        lam: float = 0.35,
        mu: float = -0.34,
    ) -> None:
        if iterations <= 0:
            return

        vertices = mesh.vertices.copy()
        neighbors = mesh.vertex_neighbors
        sharp_mask = np.zeros(len(vertices), dtype=bool)

        if len(mesh.face_adjacency) > 0 and hasattr(mesh, "face_adjacency_angles"):
            sharp_adj = np.where(np.degrees(mesh.face_adjacency_angles) > sharp_angle_deg)[0]
            sharp_faces = mesh.face_adjacency[sharp_adj].ravel()
            sharp_vertices = np.unique(mesh.faces[sharp_faces].ravel())
            sharp_mask[sharp_vertices] = True

        for _ in range(iterations):
            forward = vertices.copy()
            for vidx, n in enumerate(neighbors):
                if sharp_mask[vidx] or not n:
                    continue
                n_idx = np.fromiter(n, dtype=np.int64, count=len(n))
                forward[vidx] = vertices[vidx] + lam * (vertices[n_idx].mean(axis=0) - vertices[vidx])
            backward = forward.copy()
            for vidx, n in enumerate(neighbors):
                if sharp_mask[vidx] or not n:
                    continue
                n_idx = np.fromiter(n, dtype=np.int64, count=len(n))
                backward[vidx] = forward[vidx] + mu * (forward[n_idx].mean(axis=0) - forward[vidx])
            vertices = backward

        mesh.vertices = vertices
        mesh.rezero()

    @staticmethod
    def _orient_normals_outward(vertices: np.ndarray, normals: np.ndarray) -> np.ndarray:
        center = vertices.mean(axis=0)
        outward = vertices - center
        signs = np.sign(np.einsum("ij,ij->i", outward, normals))
        if np.count_nonzero(signs < 0) > np.count_nonzero(signs >= 0):
            return -normals
        return normals

    @staticmethod
    def _voxel_downsample(
        vertices: np.ndarray,
        normals: np.ndarray,
        voxel_size_mm: float,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        if voxel_size_mm <= 0:
            idx = np.arange(vertices.shape[0], dtype=np.int64)
            return vertices.copy(), normals.copy(), idx
        q = np.floor(vertices / voxel_size_mm).astype(np.int64)
        _, keep = np.unique(q, axis=0, return_index=True)
        keep = np.sort(keep)
        return vertices[keep], normals[keep], keep

    def run(self, stl_path: str | Path) -> ProcessedMesh:
        stl_path = Path(stl_path)
        self._emit(0.01, "Load STL")

        loaded = trimesh.load_mesh(str(stl_path), process=False, force="mesh", skip_materials=True)
        if isinstance(loaded, trimesh.Scene):
            mesh = trimesh.util.concatenate(tuple(loaded.geometry.values()))
        else:
            mesh = loaded

        if not isinstance(mesh, trimesh.Trimesh):
            raise ValueError("Input STL could not be interpreted as triangle mesh")
        if mesh.faces.size == 0 or mesh.vertices.size == 0:
            raise ValueError("Input STL is empty")

        self._emit(0.1, "Repair mesh")
        non_manifold_before = self._count_non_manifold_edges(mesh)
        for fn_name in (
            "remove_unreferenced_vertices",
            "remove_duplicate_faces",
            "remove_degenerate_faces",
            "merge_vertices",
        ):
            fn = getattr(mesh, fn_name, None)
            if callable(fn):
                try:
                    fn()
                except TypeError:
                    fn(digits_vertex=8)  # trimesh <=4.2 compatibility

        trimesh.repair.fix_normals(mesh, multibody=True)
        try:
            trimesh.repair.fix_inversion(mesh, multibody=True)
        except TypeError:
            trimesh.repair.fix_inversion(mesh)
        trimesh.repair.fill_holes(mesh)
        mesh.remove_unreferenced_vertices()

        if self.config.enable_smoothing:
            self._emit(0.2, "Feature-aware smoothing")
            self._feature_aware_smooth(
                mesh=mesh,
                iterations=self.config.profile.smoothing_iterations,
                sharp_angle_deg=self.config.profile.smoothing_sharp_angle_deg,
            )

        self._emit(0.35, "Compute normals")
        normals = np.asarray(mesh.vertex_normals, dtype=np.float64)
        vertices = np.asarray(mesh.vertices, dtype=np.float64)
        normals = self._orient_normals_outward(vertices, normals)

        self._emit(0.45, "Sampling points")
        sampled_points, sampled_normals, sampled_to_vertex = self._voxel_downsample(
            vertices=vertices,
            normals=normals,
            voxel_size_mm=self.config.profile.voxel_size_mm,
        )

        non_manifold_after = self._count_non_manifold_edges(mesh)
        metadata = {
            "vertex_count": int(vertices.shape[0]),
            "face_count": int(mesh.faces.shape[0]),
            "sampled_points": int(sampled_points.shape[0]),
            "watertight": bool(mesh.is_watertight),
            "euler_number": int(mesh.euler_number),
            "non_manifold_edges_before": non_manifold_before,
            "non_manifold_edges_after": non_manifold_after,
        }

        self._emit(0.5, "Preprocessing done")
        return ProcessedMesh(
            mesh=mesh,
            vertices=vertices,
            vertex_normals=normals,
            sampled_points=sampled_points,
            sampled_normals=sampled_normals,
            sampled_to_vertex_map=sampled_to_vertex.astype(np.int64),
            metadata=metadata,
        )

