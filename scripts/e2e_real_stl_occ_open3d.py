from __future__ import annotations

import argparse
import json
import math
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import open3d as o3d
import trimesh

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from stl_reconstructor.config import QualityMode, ReconstructionConfig
from stl_reconstructor.occ_tessellate import tessellate_shape
from stl_reconstructor.pipeline import ReconstructionPipeline


def make_helix_tube_stl(
    output: Path,
    major_radius: float = 8.0,
    tube_radius: float = 1.4,
    pitch: float = 2.0,
    turns: float = 7.0,
    slices: int = 340,
    ring_segments: int = 24,
) -> None:
    t = np.linspace(0.0, 2.0 * math.pi * turns, slices)
    centers = np.column_stack(
        [
            major_radius * np.cos(t),
            major_radius * np.sin(t),
            (pitch / (2.0 * math.pi)) * t,
        ]
    )
    tangents = np.gradient(centers, axis=0)
    tangents /= np.maximum(np.linalg.norm(tangents, axis=1, keepdims=True), 1e-9)

    rings = []
    prev_n = np.array([0.0, 0.0, 1.0], dtype=np.float64)
    for i in range(slices):
        t_vec = tangents[i]
        b_vec = np.cross(t_vec, prev_n)
        if np.linalg.norm(b_vec) < 1e-6:
            b_vec = np.cross(t_vec, np.array([1.0, 0.0, 0.0], dtype=np.float64))
        b_vec /= np.linalg.norm(b_vec)
        n_vec = np.cross(b_vec, t_vec)
        n_vec /= np.linalg.norm(n_vec)
        prev_n = n_vec
        ang = np.linspace(0.0, 2.0 * math.pi, ring_segments, endpoint=False)
        ring = centers[i] + tube_radius * (np.cos(ang)[:, None] * n_vec + np.sin(ang)[:, None] * b_vec)
        rings.append(ring)
    rings = np.asarray(rings, dtype=np.float64)

    vertices = rings.reshape(-1, 3)
    faces = []

    def vid(i: int, j: int) -> int:
        return i * ring_segments + (j % ring_segments)

    for i in range(slices - 1):
        for j in range(ring_segments):
            a = vid(i, j)
            b = vid(i, j + 1)
            c = vid(i + 1, j + 1)
            d = vid(i + 1, j)
            faces.append([a, b, c])
            faces.append([a, c, d])

    start_idx = len(vertices)
    vertices = np.vstack([vertices, centers[0], centers[-1]])
    for j in range(ring_segments):
        faces.append([start_idx, vid(0, j + 1), vid(0, j)])
    for j in range(ring_segments):
        faces.append([start_idx + 1, vid(slices - 1, j), vid(slices - 1, j + 1)])

    mesh = trimesh.Trimesh(vertices=vertices, faces=np.asarray(faces, dtype=np.int32), process=True)
    mesh.export(output)


def make_primitives_stl(output: Path) -> None:
    cyl = trimesh.creation.cylinder(radius=10.0, height=28.0, sections=120)
    box = trimesh.creation.box(extents=[30.0, 22.0, 8.0])
    box.apply_translation([0.0, 0.0, -18.0])
    combo = trimesh.util.concatenate([cyl, box])
    combo.export(output)


def make_combo_stl(output: Path) -> None:
    sphere = trimesh.creation.icosphere(subdivisions=4, radius=10.0)
    cone = trimesh.creation.cone(radius=8.0, height=22.0, sections=96)
    torus = trimesh.creation.torus(major_radius=14.0, minor_radius=2.5, major_sections=120, minor_sections=48)
    cone.apply_translation([28.0, 0.0, 0.0])
    torus.apply_translation([-30.0, 0.0, 0.0])
    all_mesh = trimesh.util.concatenate([sphere, cone, torus])
    all_mesh.export(output)


@dataclass
class CaseResult:
    name: str
    stl: str
    step: str | None
    json_report: str | None
    quality: str
    success: bool
    error: str | None
    elapsed_sec: float | None
    brep_valid: bool | None
    brep_watertight: bool | None
    feature_count: int
    primitive_counts: dict[str, int]
    source_triangles: int
    recon_triangles: int


def run_case(name: str, stl: Path, quality: QualityMode, out_step: Path, enable_preview: bool = True) -> CaseResult:
    src_mesh = o3d.io.read_triangle_mesh(str(stl))
    source_triangles = int(np.asarray(src_mesh.triangles).shape[0])
    cfg = ReconstructionConfig(quality_mode=quality, export_tolerance_mm=0.01)
    pipeline = ReconstructionPipeline(config=cfg, progress=lambda p, m: print(f"{name:>18} | {p*100:6.2f}% | {m}"))
    try:
        result = pipeline.run(stl, out_step)
    except Exception as exc:
        return CaseResult(
            name=name,
            stl=str(stl),
            step=None,
            json_report=None,
            quality=quality.value,
            success=False,
            error=str(exc),
            elapsed_sec=None,
            brep_valid=None,
            brep_watertight=None,
            feature_count=0,
            primitive_counts={},
            source_triangles=source_triangles,
            recon_triangles=0,
        )

    shape = result.brep.solid or result.brep.shell or (result.brep.faces[0] if result.brep.faces else None)
    recon_triangles = 0
    if shape is not None:
        v, f = tessellate_shape(shape, linear_deflection=0.2, angular_deflection=0.3)
        if v.size > 0 and f.size > 0:
            recon_triangles = int(f.shape[0])
            if enable_preview and quality != QualityMode.ULTRA and recon_triangles <= 500_000:
                try:
                    preview = o3d.geometry.TriangleMesh(
                        o3d.utility.Vector3dVector(v),
                        o3d.utility.Vector3iVector(f),
                    )
                    preview.compute_vertex_normals()
                    o3d.io.write_triangle_mesh(str(out_step.with_suffix(".preview.ply")), preview, write_ascii=False)
                except Exception as exc:
                    print(f"[preview-skip] {name}: {exc}")

    return CaseResult(
        name=name,
        stl=str(stl),
        step=str(result.output_step),
        json_report=str(result.output_step.with_suffix(".json")),
        quality=quality.value,
        success=True,
        error=None,
        elapsed_sec=float(result.elapsed_sec),
        brep_valid=bool(result.brep.valid),
        brep_watertight=bool(result.brep.watertight),
        feature_count=len(result.features),
        primitive_counts=dict(result.stats.get("primitive_counts", {})),
        source_triangles=source_triangles,
        recon_triangles=recon_triangles,
    )


def main() -> int:
    default_out = Path("C:/build/stl_reconstructor_e2e") if os.name == "nt" else (ROOT / "artifacts" / "e2e")
    parser = argparse.ArgumentParser(description="End-to-end STL/OCC/Open3D validation runner")
    parser.add_argument("--out-dir", default=str(default_out), help="Output directory")
    parser.add_argument("--no-preview", action="store_true", help="Skip Open3D preview export")
    args = parser.parse_args()
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    input_dir = out_dir / "inputs"
    input_dir.mkdir(parents=True, exist_ok=True)

    stl_a = input_dir / "primitives.stl"
    stl_b = input_dir / "combo.stl"
    stl_c = input_dir / "helix_thread_like.stl"
    make_primitives_stl(stl_a)
    make_combo_stl(stl_b)
    make_helix_tube_stl(stl_c)

    enable_preview = not args.no_preview
    results = [
        run_case("primitives_high", stl_a, QualityMode.HIGH, out_dir / "primitives_high.step", enable_preview),
        run_case("combo_high", stl_b, QualityMode.HIGH, out_dir / "combo_high.step", enable_preview),
        run_case("helix_ultra", stl_c, QualityMode.ULTRA, out_dir / "helix_ultra.step", enable_preview),
    ]

    payload = {
        "runner": "e2e_real_stl_occ_open3d",
        "result_count": len(results),
        "results": [asdict(r) for r in results],
    }
    report = out_dir / "e2e_summary.json"
    report.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"\nE2E summary written to: {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
