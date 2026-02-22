from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable

import numpy as np
from scipy.spatial import ConvexHull, cKDTree

from .fitting import orthonormal_basis
from .models import BRepBuildInfo, PrimitiveFeature, PrimitiveType, ProcessedMesh
from .occ_runtime import occ
from .segmentation import SegmentationOutput

ProgressCallback = Callable[[float, str], None]

BRepBuilderAPI = occ.module("BRepBuilderAPI")
BRepCheck = occ.module("BRepCheck")
BRepOffsetAPI = occ.module("BRepOffsetAPI")
Geom = occ.module("Geom")
GeomAPI = occ.module("GeomAPI")
GeomAbs = occ.module("GeomAbs")
gp = occ.module("gp")
ShapeFix = occ.module("ShapeFix")
TopAbs = occ.module("TopAbs")
TopExp = occ.module("TopExp")
TopoDS_module = occ.module("TopoDS")
TColgp = occ.module("TColgp")

BRepBuilderAPI_MakeEdge = BRepBuilderAPI.BRepBuilderAPI_MakeEdge
BRepBuilderAPI_MakeFace = BRepBuilderAPI.BRepBuilderAPI_MakeFace
BRepBuilderAPI_MakePolygon = BRepBuilderAPI.BRepBuilderAPI_MakePolygon
BRepBuilderAPI_MakeSolid = BRepBuilderAPI.BRepBuilderAPI_MakeSolid
BRepBuilderAPI_MakeWire = BRepBuilderAPI.BRepBuilderAPI_MakeWire
BRepBuilderAPI_Sewing = BRepBuilderAPI.BRepBuilderAPI_Sewing
BRepCheck_Analyzer = BRepCheck.BRepCheck_Analyzer
BRepOffsetAPI_MakePipeShell = BRepOffsetAPI.BRepOffsetAPI_MakePipeShell
Geom_ConicalSurface = Geom.Geom_ConicalSurface
Geom_CylindricalSurface = Geom.Geom_CylindricalSurface
Geom_SphericalSurface = Geom.Geom_SphericalSurface
Geom_ToroidalSurface = Geom.Geom_ToroidalSurface
GeomAPI_PointsToBSpline = GeomAPI.GeomAPI_PointsToBSpline
GeomAPI_PointsToBSplineSurface = GeomAPI.GeomAPI_PointsToBSplineSurface
GeomAbs_C2 = GeomAbs.GeomAbs_C2
gp_Ax3 = gp.gp_Ax3
gp_Dir = gp.gp_Dir
gp_Pnt = gp.gp_Pnt
ShapeFix_Shell = ShapeFix.ShapeFix_Shell
ShapeFix_Solid = ShapeFix.ShapeFix_Solid
TopAbs_SHELL = TopAbs.TopAbs_SHELL
TopExp_Explorer = TopExp.TopExp_Explorer
TColgp_Array1OfPnt = TColgp.TColgp_Array1OfPnt
TColgp_Array2OfPnt = TColgp.TColgp_Array2OfPnt

if occ.name == "pythonocc":
    _topods = TopoDS_module.topods

    def _to_shell(shape):
        return _topods.Shell(shape)

else:
    _topods_cls = getattr(TopoDS_module, "TopoDS", TopoDS_module)

    def _to_shell(shape):
        return _topods_cls.Shell_s(shape)


def _pnt(v: np.ndarray) -> gp_Pnt:
    return gp_Pnt(float(v[0]), float(v[1]), float(v[2]))


def _dir(v: np.ndarray) -> gp_Dir:
    n = np.linalg.norm(v)
    if n <= 1e-12:
        raise ValueError("Direction vector must be non-zero")
    return gp_Dir(float(v[0] / n), float(v[1] / n), float(v[2] / n))


@dataclass
class FeatureFace:
    feature: PrimitiveFeature
    face: object


class BRepReconstructor:
    def __init__(
        self,
        tolerance_mm: float = 0.01,
        prefer_analytic_surfaces: bool = True,
        progress: ProgressCallback | None = None,
    ) -> None:
        self.tol = float(max(1e-6, tolerance_mm))
        self.prefer_analytic_surfaces = bool(prefer_analytic_surfaces)
        self.progress = progress

    def _emit(self, fraction: float, message: str) -> None:
        if self.progress:
            self.progress(float(max(0.0, min(1.0, fraction))), message)

    def _plane_face(self, feature: PrimitiveFeature, points: np.ndarray) -> object | None:
        if points.shape[0] < 3:
            return None
        n = feature.params["normal"]
        origin = feature.params["point"]
        u, v = orthonormal_basis(n)
        local = points - origin
        uv = np.column_stack([local @ u, local @ v])
        if uv.shape[0] < 3:
            return None
        try:
            hull = ConvexHull(uv)
            boundary_idx = hull.vertices
        except Exception:
            boundary_idx = np.unique(np.argsort(np.linalg.norm(uv, axis=1))[-8:])
        if boundary_idx.size < 3:
            return None

        poly = BRepBuilderAPI_MakePolygon()
        for idx in boundary_idx:
            p3 = origin + uv[idx, 0] * u + uv[idx, 1] * v
            poly.Add(_pnt(p3))
        poly.Close()
        wire = poly.Wire()
        return BRepBuilderAPI_MakeFace(wire, True).Face()

    @staticmethod
    def _unwrap_angles(theta: np.ndarray) -> tuple[float, float]:
        if theta.size == 0:
            return 0.0, 2.0 * math.pi
        unwrapped = np.unwrap(theta)
        lo = float(unwrapped.min())
        hi = float(unwrapped.max())
        span = hi - lo
        if span > 1.95 * math.pi:
            return 0.0, 2.0 * math.pi
        return lo, hi

    def _cylinder_face(self, feature: PrimitiveFeature, points: np.ndarray) -> object | None:
        if points.shape[0] < 10:
            return None
        axis_point = feature.params["axis_point"]
        axis_dir = feature.params["axis_dir"]
        radius = float(feature.params["radius"])
        if radius <= 0:
            return None
        u, w = orthonormal_basis(axis_dir)
        q = points - axis_point
        x = q @ u
        y = q @ w
        z = q @ axis_dir
        theta = np.arctan2(y, x)
        umin, umax = self._unwrap_angles(theta)
        vmin = float(z.min()) - self.tol
        vmax = float(z.max()) + self.tol
        axis = gp_Ax3(_pnt(axis_point), _dir(axis_dir), _dir(u))
        surf = Geom_CylindricalSurface(axis, radius)
        return BRepBuilderAPI_MakeFace(surf, umin, umax, vmin, vmax, self.tol).Face()

    def _sphere_face(self, feature: PrimitiveFeature, points: np.ndarray) -> object | None:
        if points.shape[0] < 12:
            return None
        center = feature.params["center"]
        radius = float(feature.params["radius"])
        if radius <= 0:
            return None

        axis_dir = np.array([0.0, 0.0, 1.0], dtype=np.float64)
        u, w = orthonormal_basis(axis_dir)
        q = (points - center) / radius
        lat = np.arcsin(np.clip(q @ axis_dir, -1.0, 1.0))
        lon = np.arctan2(q @ w, q @ u)
        umin, umax = self._unwrap_angles(lon)
        vmin = float(max(-math.pi / 2, np.min(lat) - 0.01))
        vmax = float(min(math.pi / 2, np.max(lat) + 0.01))
        ax3 = gp_Ax3(_pnt(center), _dir(axis_dir), _dir(u))
        surf = Geom_SphericalSurface(ax3, radius)
        return BRepBuilderAPI_MakeFace(surf, umin, umax, vmin, vmax, self.tol).Face()

    def _cone_face(self, feature: PrimitiveFeature, points: np.ndarray) -> object | None:
        if points.shape[0] < 12:
            return None
        apex = feature.params["apex"]
        axis_dir = feature.params["axis_dir"]
        angle = float(feature.params["half_angle_rad"])
        angle = float(np.clip(angle, 1e-6, math.radians(89.0)))
        t = (points - apex) @ axis_dir
        tmin = float(t.min())
        tmax = float(t.max())
        if abs(tmax - tmin) < 1e-6:
            return None
        ref_t = tmin + 0.15 * (tmax - tmin)
        ref_t = ref_t if abs(ref_t) > 1e-6 else tmin + 1e-3
        location = apex + ref_t * axis_dir
        ref_radius = abs(ref_t * math.tan(angle))
        if ref_radius < 1e-6:
            ref_radius = 1e-6

        uvec, wvec = orthonormal_basis(axis_dir)
        q = points - location
        u_angles = np.arctan2(q @ wvec, q @ uvec)
        umin, umax = self._unwrap_angles(u_angles)
        v_param = (points - location) @ axis_dir
        vmin = float(v_param.min()) - self.tol
        vmax = float(v_param.max()) + self.tol

        ax3 = gp_Ax3(_pnt(location), _dir(axis_dir), _dir(uvec))
        surf = Geom_ConicalSurface(ax3, angle, ref_radius)
        return BRepBuilderAPI_MakeFace(surf, umin, umax, vmin, vmax, self.tol).Face()

    def _torus_face(self, feature: PrimitiveFeature, points: np.ndarray) -> object | None:
        if points.shape[0] < 20:
            return None
        center = feature.params["center"]
        axis_dir = feature.params["axis_dir"]
        major = float(feature.params["major_radius"])
        minor = float(feature.params["minor_radius"])
        if major <= 1e-6 or minor <= 1e-6:
            return None
        uvec, wvec = orthonormal_basis(axis_dir)
        q = points - center
        z = q @ axis_dir
        qxy = q - np.outer(z, axis_dir)
        u_angle = np.arctan2(qxy @ wvec, qxy @ uvec)
        rr = np.linalg.norm(qxy, axis=1)
        v_angle = np.arctan2(z, rr - major)
        umin, umax = self._unwrap_angles(u_angle)
        vmin, vmax = self._unwrap_angles(v_angle)
        ax3 = gp_Ax3(_pnt(center), _dir(axis_dir), _dir(uvec))
        surf = Geom_ToroidalSurface(ax3, major, minor)
        return BRepBuilderAPI_MakeFace(surf, umin, umax, vmin, vmax, self.tol).Face()

    def _helix_surface(self, feature: PrimitiveFeature, points: np.ndarray) -> object | None:
        if points.shape[0] < 30:
            return None
        axis_point = feature.params["axis_point"]
        axis_dir = feature.params["axis_dir"]
        pitch = float(feature.params["pitch"])
        major_d = float(feature.params["major_diameter"])
        minor_d = float(feature.params["minor_diameter"])
        mean_r = float(feature.params["mean_radius"])
        if pitch <= 1e-6 or mean_r <= 1e-6:
            return None

        uvec, wvec = orthonormal_basis(axis_dir)
        q = points - axis_point
        z_vals = q @ axis_dir
        x = q @ uvec
        y = q @ wvec
        theta = np.unwrap(np.arctan2(y, x))
        theta_min = float(theta.min())
        theta_max = float(theta.max())
        turns = max(1.0, (theta_max - theta_min) / (2.0 * math.pi))
        n_samples = int(max(80, min(720, turns * 180)))
        theta_s = np.linspace(theta_min, theta_max, n_samples)
        z0 = float(np.median(z_vals - (pitch / (2.0 * math.pi)) * theta))
        z_s = z0 + (pitch / (2.0 * math.pi)) * theta_s

        helix_pts = []
        for th, zz in zip(theta_s, z_s):
            pt = axis_point + zz * axis_dir + mean_r * (math.cos(th) * uvec + math.sin(th) * wvec)
            helix_pts.append(_pnt(pt))

        spline_builder = GeomAPI_PointsToBSpline()
        arr = TColgp_Array1OfPnt(1, len(helix_pts))
        for i, p in enumerate(helix_pts, start=1):
            arr.SetValue(i, p)
        spline_builder.Init(arr)
        curve = spline_builder.Curve()
        spine_edge = BRepBuilderAPI_MakeEdge(curve).Edge()
        spine_wire = BRepBuilderAPI_MakeWire(spine_edge).Wire()

        depth = max(1e-6, (major_d - minor_d) * 0.5)
        half_width = max(depth * 0.8, pitch * 0.25)
        start_center = axis_point + z_s[0] * axis_dir + mean_r * (math.cos(theta_s[0]) * uvec + math.sin(theta_s[0]) * wvec)
        tangent = (pitch / (2.0 * math.pi)) * axis_dir + mean_r * (
            -math.sin(theta_s[0]) * uvec + math.cos(theta_s[0]) * wvec
        )
        tangent = tangent / np.linalg.norm(tangent)
        n1 = np.cross(tangent, axis_dir)
        n1 = n1 / max(np.linalg.norm(n1), 1e-9)
        n2 = np.cross(tangent, n1)
        n2 = n2 / max(np.linalg.norm(n2), 1e-9)

        p_a = start_center + half_width * n1
        p_b = start_center - half_width * n1
        p_c = start_center - depth * n2
        profile = BRepBuilderAPI_MakePolygon()
        profile.Add(_pnt(p_a))
        profile.Add(_pnt(p_b))
        profile.Add(_pnt(p_c))
        profile.Close()
        profile_wire = profile.Wire()

        pipe = BRepOffsetAPI_MakePipeShell(spine_wire)
        pipe.Add(profile_wire, False, False)
        pipe.SetMode(True)
        pipe.Build()
        if not pipe.IsDone():
            return None
        pipe.MakeSolid()
        return pipe.Shape()

    def _freeform_face(self, points: np.ndarray) -> object | None:
        if points.shape[0] < 25:
            return None
        center = points.mean(axis=0)
        centered = points - center
        _, _, vh = np.linalg.svd(centered, full_matrices=False)
        u_axis = vh[0]
        v_axis = vh[1]
        uv = np.column_stack([centered @ u_axis, centered @ v_axis])

        grid = int(max(8, min(26, math.sqrt(points.shape[0]) * 0.5)))
        u_lin = np.linspace(float(uv[:, 0].min()), float(uv[:, 0].max()), grid)
        v_lin = np.linspace(float(uv[:, 1].min()), float(uv[:, 1].max()), grid)
        tree = cKDTree(uv)

        arr = TColgp_Array2OfPnt(1, grid, 1, grid)
        for i, uu in enumerate(u_lin, start=1):
            for j, vv in enumerate(v_lin, start=1):
                _, idx = tree.query(np.array([uu, vv]), k=1)
                arr.SetValue(i, j, _pnt(points[int(idx)]))

        surf_builder = GeomAPI_PointsToBSplineSurface()
        surf_builder.Init(arr, 3, 8, GeomAbs_C2, max(0.01, self.tol * 2.0))
        surf = surf_builder.Surface()
        try:
            return BRepBuilderAPI_MakeFace(surf, self.tol).Face()
        except Exception:
            return BRepBuilderAPI_MakeFace(surf, 0.0, 1.0, 0.0, 1.0, self.tol).Face()

    def _face_for_feature(self, feature: PrimitiveFeature, points: np.ndarray) -> object | None:
        if feature.primitive == PrimitiveType.PLANE:
            return self._plane_face(feature, points)
        if feature.primitive == PrimitiveType.CYLINDER:
            return self._cylinder_face(feature, points)
        if feature.primitive == PrimitiveType.SPHERE:
            return self._sphere_face(feature, points)
        if feature.primitive == PrimitiveType.CONE:
            return self._cone_face(feature, points)
        if feature.primitive == PrimitiveType.TORUS:
            return self._torus_face(feature, points)
        if feature.primitive == PrimitiveType.HELIX:
            face = self._helix_surface(feature, points)
            return face if face is not None else self._freeform_face(points)
        if feature.primitive == PrimitiveType.FREEFORM:
            return self._freeform_face(points)
        return self._freeform_face(points)

    def _mesh_fallback_build(self, processed: ProcessedMesh) -> BRepBuildInfo:
        """Build a faceted but shape-faithful B-Rep from the repaired mesh triangles."""
        self._emit(0.90, "Fallback: build faceted B-Rep from mesh")
        vertices = np.asarray(processed.mesh.vertices, dtype=np.float64)
        faces_idx = np.asarray(processed.mesh.faces, dtype=np.int64)
        if vertices.size == 0 or faces_idx.size == 0:
            return BRepBuildInfo(
                solid=None,
                shell=None,
                faces=[],
                valid=False,
                watertight=False,
                self_intersection_free=False,
                diagnostics=["Fallback failed: mesh has no vertices/faces."],
            )

        faces = []
        for i, tri in enumerate(faces_idx):
            a = vertices[int(tri[0])]
            b = vertices[int(tri[1])]
            c = vertices[int(tri[2])]
            poly = BRepBuilderAPI_MakePolygon()
            poly.Add(_pnt(a))
            poly.Add(_pnt(b))
            poly.Add(_pnt(c))
            poly.Close()
            wire = poly.Wire()
            mk_face = BRepBuilderAPI_MakeFace(wire, True)
            if mk_face.IsDone():
                faces.append(mk_face.Face())
            if i % 2500 == 0:
                self._emit(0.90 + min(0.05, 0.05 * (i + 1) / max(1, len(faces_idx))), "Fallback triangulated faces")

        if not faces:
            return BRepBuildInfo(
                solid=None,
                shell=None,
                faces=[],
                valid=False,
                watertight=False,
                self_intersection_free=False,
                diagnostics=["Fallback failed: could not create triangle faces."],
            )

        sewing = BRepBuilderAPI_Sewing(self.tol)
        for f in faces:
            sewing.Add(f)
        sewing.Perform()
        sewed = sewing.SewedShape()

        shell = None
        if sewed.ShapeType() == TopAbs_SHELL:
            shell = _to_shell(sewed)
        else:
            explorer = TopExp_Explorer(sewed, TopAbs_SHELL)
            if explorer.More():
                shell = _to_shell(explorer.Current())

        fixed_shell = None
        solid = None
        if shell is not None:
            shell_fixer = ShapeFix_Shell(shell)
            shell_fixer.Perform()
            fixed_shell = shell_fixer.Shell()

            solid_builder = BRepBuilderAPI_MakeSolid()
            solid_builder.Add(fixed_shell)
            if solid_builder.IsDone():
                solid = solid_builder.Solid()
                solid_fixer = ShapeFix_Solid(solid)
                solid_fixer.Perform()
                solid = solid_fixer.Solid()

        check_shape = solid if solid is not None else (fixed_shell if fixed_shell is not None else sewed)
        analyzer = BRepCheck_Analyzer(check_shape)
        valid = bool(analyzer.IsValid())
        watertight = bool(sewing.NbFreeEdges() == 0 and fixed_shell is not None)
        return BRepBuildInfo(
            solid=solid,
            shell=fixed_shell,
            faces=faces,
            valid=valid,
            watertight=watertight,
            self_intersection_free=valid,
            diagnostics=[
                "Used faceted mesh fallback B-Rep for shape fidelity.",
                f"Fallback free edges: {int(sewing.NbFreeEdges())}",
            ],
        )

    def build(self, processed: ProcessedMesh, seg: SegmentationOutput) -> BRepBuildInfo:
        self._emit(0.78, "Build analytical OCC faces")
        faces = []
        diagnostics: list[str] = []

        sampled_points = processed.sampled_points
        for i, feature in enumerate(seg.features):
            pts = sampled_points[feature.inlier_indices]
            try:
                face = self._face_for_feature(feature, pts)
            except Exception as exc:
                diagnostics.append(f"Feature {feature.feature_id} ({feature.primitive.value}) failed: {exc}")
                face = None
            if face is not None:
                faces.append(face)
            if i % 3 == 0:
                self._emit(0.78 + min(0.10, 0.10 * (i + 1) / max(1, len(seg.features))), "Fitting OCC faces")

        if not faces:
            return BRepBuildInfo(
                solid=None,
                shell=None,
                faces=[],
                valid=False,
                watertight=False,
                self_intersection_free=False,
                diagnostics=diagnostics + ["No analytical faces could be reconstructed."],
            )

        self._emit(0.89, "Sewing and topology healing")
        sewing = BRepBuilderAPI_Sewing(self.tol)
        for f in faces:
            sewing.Add(f)
        sewing.Perform()
        sewed = sewing.SewedShape()

        shell = None
        if sewed.ShapeType() == TopAbs_SHELL:
            shell = _to_shell(sewed)
        else:
            explorer = TopExp_Explorer(sewed, TopAbs_SHELL)
            if explorer.More():
                shell = _to_shell(explorer.Current())

        fixed_shell = None
        solid = None
        if shell is not None:
            shell_fixer = ShapeFix_Shell(shell)
            shell_fixer.Perform()
            fixed_shell = shell_fixer.Shell()

            solid_builder = BRepBuilderAPI_MakeSolid()
            solid_builder.Add(fixed_shell)
            if solid_builder.IsDone():
                solid = solid_builder.Solid()
                solid_fixer = ShapeFix_Solid(solid)
                solid_fixer.Perform()
                solid = solid_fixer.Solid()

        check_shape = solid if solid is not None else (fixed_shell if fixed_shell is not None else sewed)
        analyzer = BRepCheck_Analyzer(check_shape)
        valid = bool(analyzer.IsValid())
        watertight = bool(sewing.NbFreeEdges() == 0 and fixed_shell is not None)
        self_intersection_free = valid
        result = BRepBuildInfo(
            solid=solid,
            shell=fixed_shell,
            faces=faces,
            valid=valid,
            watertight=watertight,
            self_intersection_free=self_intersection_free,
            diagnostics=diagnostics,
        )
        total_pts = max(1, int(processed.sampled_points.shape[0]))
        covered = int(sum(f.inlier_indices.size for f in seg.features if f.primitive != PrimitiveType.FREEFORM))
        coverage = float(covered / total_pts)
        if self.prefer_analytic_surfaces:
            # V3 mode: prefer analytical surfaces; fallback only if absolutely no usable topology.
            if (result.shell is not None) or (result.solid is not None) or len(result.faces) > 0:
                self._emit(0.96, "B-Rep reconstruction complete (analytical preferred)")
                return result
            fallback = self._mesh_fallback_build(processed)
            fallback.diagnostics = result.diagnostics + [
                f"Analytical preferred but invalid/incomplete (valid={result.valid}, watertight={result.watertight}, coverage={coverage:.3f})."
            ] + fallback.diagnostics
            self._emit(0.96, "B-Rep reconstruction complete (fallback)")
            return fallback

        if (not result.valid) or (not result.watertight) or (coverage < 0.65):
            fallback = self._mesh_fallback_build(processed)
            fallback.diagnostics = result.diagnostics + [
                f"Analytical build degraded (valid={result.valid}, watertight={result.watertight}, coverage={coverage:.3f})."
            ] + fallback.diagnostics
            self._emit(0.96, "B-Rep reconstruction complete (fallback)")
            return fallback

        self._emit(0.96, "B-Rep reconstruction complete")
        return result
