from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Callable

import numpy as np
from scipy.optimize import least_squares


def normalize(v: np.ndarray, eps: float = 1e-12) -> np.ndarray:
    n = np.linalg.norm(v)
    if n < eps:
        return v * 0.0
    return v / n


def orthonormal_basis(z_axis: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    z = normalize(z_axis)
    helper = np.array([1.0, 0.0, 0.0], dtype=np.float64)
    if abs(np.dot(z, helper)) > 0.9:
        helper = np.array([0.0, 1.0, 0.0], dtype=np.float64)
    x = normalize(np.cross(z, helper))
    y = normalize(np.cross(z, x))
    return x, y


def pca_axis(points: np.ndarray, idx: int = 0) -> np.ndarray:
    centered = points - points.mean(axis=0)
    cov = centered.T @ centered / max(1, points.shape[0] - 1)
    vals, vecs = np.linalg.eigh(cov)
    order = np.argsort(vals)[::-1]
    return normalize(vecs[:, order[idx]])


def fit_plane_from_points(points: np.ndarray) -> dict[str, Any] | None:
    if points.shape[0] < 3:
        return None
    centered = points - points.mean(axis=0)
    _, _, vh = np.linalg.svd(centered, full_matrices=False)
    normal = normalize(vh[-1])
    d = -float(np.dot(normal, points.mean(axis=0)))
    return {"normal": normal, "d": d, "point": points.mean(axis=0)}


def plane_distances(points: np.ndarray, model: dict[str, Any]) -> np.ndarray:
    n = model["normal"]
    d = model["d"]
    return np.abs(points @ n + d)


def fit_sphere_algebraic(points: np.ndarray) -> dict[str, Any] | None:
    if points.shape[0] < 4:
        return None
    a = np.hstack([2.0 * points, np.ones((points.shape[0], 1), dtype=np.float64)])
    b = np.sum(points**2, axis=1)
    try:
        x, *_ = np.linalg.lstsq(a, b, rcond=None)
    except np.linalg.LinAlgError:
        return None
    center = x[:3]
    radius_sq = float(np.dot(center, center) + x[3])
    if radius_sq <= 0:
        return None
    return {"center": center, "radius": math.sqrt(radius_sq)}


def sphere_distances(points: np.ndarray, model: dict[str, Any]) -> np.ndarray:
    c = model["center"]
    r = model["radius"]
    return np.abs(np.linalg.norm(points - c, axis=1) - r)


def _fit_circle_2d(points_2d: np.ndarray) -> tuple[np.ndarray, float] | None:
    if points_2d.shape[0] < 3:
        return None
    x = points_2d[:, 0]
    y = points_2d[:, 1]
    a = np.column_stack([2.0 * x, 2.0 * y, np.ones_like(x)])
    b = x * x + y * y
    try:
        sol, *_ = np.linalg.lstsq(a, b, rcond=None)
    except np.linalg.LinAlgError:
        return None
    center = sol[:2]
    radius_sq = float(center[0] ** 2 + center[1] ** 2 + sol[2])
    if radius_sq <= 0:
        return None
    return center, math.sqrt(radius_sq)


def fit_cylinder(points: np.ndarray) -> dict[str, Any] | None:
    if points.shape[0] < 6:
        return None

    axis_dir = pca_axis(points, idx=0)
    basis_u, basis_v = orthonormal_basis(axis_dir)
    local = points - points.mean(axis=0)
    x = local @ basis_u
    y = local @ basis_v
    z = local @ axis_dir

    circle = _fit_circle_2d(np.column_stack([x, y]))
    if circle is None:
        return None
    center_2d, radius0 = circle
    p0 = points.mean(axis=0) + center_2d[0] * basis_u + center_2d[1] * basis_v + z.mean() * axis_dir
    if radius0 <= 0:
        return None

    def pack(axis: np.ndarray) -> tuple[float, float]:
        ax = normalize(axis)
        theta = math.acos(max(-1.0, min(1.0, ax[2])))
        phi = math.atan2(ax[1], ax[0])
        return theta, phi

    def unpack(theta: float, phi: float) -> np.ndarray:
        return normalize(
            np.array(
                [
                    math.sin(theta) * math.cos(phi),
                    math.sin(theta) * math.sin(phi),
                    math.cos(theta),
                ],
                dtype=np.float64,
            )
        )

    theta0, phi0 = pack(axis_dir)
    x0 = np.array([*p0, theta0, phi0, radius0], dtype=np.float64)

    def residual(vec: np.ndarray) -> np.ndarray:
        p = vec[:3]
        axis = unpack(vec[3], vec[4])
        radius = abs(float(vec[5]))
        q = points - p
        axial = np.outer(q @ axis, axis)
        radial = q - axial
        return np.linalg.norm(radial, axis=1) - radius

    opt = least_squares(residual, x0, loss="huber", f_scale=max(1e-4, radius0 * 0.05), max_nfev=160)
    axis = unpack(opt.x[3], opt.x[4])
    radius = abs(float(opt.x[5]))
    p = opt.x[:3]
    if radius <= 1e-8:
        return None
    return {"axis_point": p, "axis_dir": axis, "radius": radius}


def cylinder_distances(points: np.ndarray, model: dict[str, Any]) -> np.ndarray:
    p = model["axis_point"]
    axis = normalize(model["axis_dir"])
    r = model["radius"]
    q = points - p
    axial = np.outer(q @ axis, axis)
    radial = q - axial
    return np.abs(np.linalg.norm(radial, axis=1) - r)


def fit_cone(points: np.ndarray) -> dict[str, Any] | None:
    if points.shape[0] < 12:
        return None
    axis = pca_axis(points, idx=0)
    centered = points - points.mean(axis=0)
    t = centered @ axis
    radial = np.linalg.norm(centered - np.outer(t, axis), axis=1)
    apex = points.mean(axis=0) + t.min() * axis
    tan_alpha = np.median(radial / np.maximum(np.abs(t - t.min()), 1e-6))
    angle = float(math.atan(max(1e-6, tan_alpha)))

    def pack(axis_vec: np.ndarray) -> tuple[float, float]:
        axis_vec = normalize(axis_vec)
        theta = math.acos(max(-1.0, min(1.0, axis_vec[2])))
        phi = math.atan2(axis_vec[1], axis_vec[0])
        return theta, phi

    def unpack(theta: float, phi: float) -> np.ndarray:
        return normalize(
            np.array(
                [
                    math.sin(theta) * math.cos(phi),
                    math.sin(theta) * math.sin(phi),
                    math.cos(theta),
                ],
                dtype=np.float64,
            )
        )

    theta0, phi0 = pack(axis)
    x0 = np.array([*apex, theta0, phi0, angle], dtype=np.float64)

    def residual(vec: np.ndarray) -> np.ndarray:
        a = vec[:3]
        v = unpack(vec[3], vec[4])
        alpha = float(np.clip(abs(vec[5]), 1e-5, math.radians(89.0)))
        q = points - a
        proj = q @ v
        radial_d = np.linalg.norm(q - np.outer(proj, v), axis=1)
        return radial_d - np.abs(proj) * math.tan(alpha)

    opt = least_squares(residual, x0, loss="huber", f_scale=0.15, max_nfev=260)
    apex_fit = opt.x[:3]
    axis_fit = unpack(opt.x[3], opt.x[4])
    alpha_fit = float(np.clip(abs(opt.x[5]), 1e-5, math.radians(89.0)))
    return {"apex": apex_fit, "axis_dir": axis_fit, "half_angle_rad": alpha_fit}


def cone_distances(points: np.ndarray, model: dict[str, Any]) -> np.ndarray:
    a = model["apex"]
    v = normalize(model["axis_dir"])
    alpha = float(model["half_angle_rad"])
    q = points - a
    proj = q @ v
    radial = np.linalg.norm(q - np.outer(proj, v), axis=1)
    return np.abs(radial - np.abs(proj) * math.tan(alpha))


def fit_torus(points: np.ndarray) -> dict[str, Any] | None:
    if points.shape[0] < 20:
        return None
    center = points.mean(axis=0)
    axis = pca_axis(points, idx=2)
    q = points - center
    z = q @ axis
    radial = np.linalg.norm(q - np.outer(z, axis), axis=1)
    major0 = float(np.median(radial))
    minor0 = float(np.median(np.sqrt((radial - major0) ** 2 + z**2)))
    if major0 <= 1e-5 or minor0 <= 1e-5:
        return None

    def pack(axis_vec: np.ndarray) -> tuple[float, float]:
        axis_vec = normalize(axis_vec)
        theta = math.acos(max(-1.0, min(1.0, axis_vec[2])))
        phi = math.atan2(axis_vec[1], axis_vec[0])
        return theta, phi

    def unpack(theta: float, phi: float) -> np.ndarray:
        return normalize(
            np.array(
                [
                    math.sin(theta) * math.cos(phi),
                    math.sin(theta) * math.sin(phi),
                    math.cos(theta),
                ],
                dtype=np.float64,
            )
        )

    theta0, phi0 = pack(axis)
    x0 = np.array([*center, theta0, phi0, major0, minor0], dtype=np.float64)

    def residual(vec: np.ndarray) -> np.ndarray:
        c = vec[:3]
        v = unpack(vec[3], vec[4])
        major = abs(float(vec[5]))
        minor = abs(float(vec[6]))
        dq = points - c
        zz = dq @ v
        rr = np.linalg.norm(dq - np.outer(zz, v), axis=1)
        return np.sqrt((rr - major) ** 2 + zz**2) - minor

    opt = least_squares(residual, x0, loss="huber", f_scale=max(1e-4, minor0 * 0.2), max_nfev=260)
    center_fit = opt.x[:3]
    axis_fit = unpack(opt.x[3], opt.x[4])
    major_fit = abs(float(opt.x[5]))
    minor_fit = abs(float(opt.x[6]))
    if major_fit <= 1e-6 or minor_fit <= 1e-6:
        return None
    return {"center": center_fit, "axis_dir": axis_fit, "major_radius": major_fit, "minor_radius": minor_fit}


def torus_distances(points: np.ndarray, model: dict[str, Any]) -> np.ndarray:
    c = model["center"]
    v = normalize(model["axis_dir"])
    major = model["major_radius"]
    minor = model["minor_radius"]
    q = points - c
    z = q @ v
    radial = np.linalg.norm(q - np.outer(z, v), axis=1)
    return np.abs(np.sqrt((radial - major) ** 2 + z**2) - minor)


def fit_helix(points: np.ndarray, base_axis: np.ndarray | None = None) -> dict[str, Any] | None:
    if points.shape[0] < 30:
        return None
    center = points.mean(axis=0)
    axis = normalize(base_axis) if base_axis is not None else pca_axis(points, idx=0)
    u, w = orthonormal_basis(axis)
    q = points - center
    z = q @ axis
    x = q @ u
    y = q @ w
    theta = np.arctan2(y, x)
    theta_unwrapped = np.unwrap(theta)
    a = np.column_stack([theta_unwrapped, np.ones_like(theta_unwrapped)])
    slope, intercept = np.linalg.lstsq(a, z, rcond=None)[0]
    pitch = float(abs(slope) * 2.0 * math.pi)
    handedness = "right" if slope >= 0 else "left"
    radius = np.linalg.norm(np.column_stack([x, y]), axis=1)
    major_radius = float(np.percentile(radius, 95))
    minor_radius = float(np.percentile(radius, 5))
    if pitch <= 1e-6 or major_radius <= 1e-6:
        return None
    predicted_z = slope * theta_unwrapped + intercept
    z_err = np.abs(z - predicted_z)
    radial_err = np.abs(radius - np.median(radius))
    residual = np.sqrt(z_err**2 + radial_err**2)
    return {
        "axis_point": center,
        "axis_dir": axis,
        "pitch": pitch,
        "handedness": handedness,
        "major_diameter": 2.0 * major_radius,
        "minor_diameter": 2.0 * minor_radius,
        "mean_radius": float(np.mean(radius)),
        "phase": float(np.mean(theta_unwrapped % (2.0 * math.pi))),
        "_residual": residual,
    }


def helix_distances(points: np.ndarray, model: dict[str, Any]) -> np.ndarray:
    axis = normalize(model["axis_dir"])
    center = model["axis_point"]
    pitch = float(model["pitch"])
    radius0 = float(model["mean_radius"])
    u, w = orthonormal_basis(axis)
    q = points - center
    z = q @ axis
    x = q @ u
    y = q @ w
    theta = np.unwrap(np.arctan2(y, x))
    slope = pitch / (2.0 * math.pi)
    z0 = np.median(z - slope * theta)
    z_res = np.abs(z - (slope * theta + z0))
    r_res = np.abs(np.sqrt(x * x + y * y) - radius0)
    return np.sqrt(z_res * z_res + r_res * r_res)


@dataclass(frozen=True)
class PrimitiveKernel:
    min_samples: int
    fit_fn: Callable[[np.ndarray], dict[str, Any] | None]
    dist_fn: Callable[[np.ndarray, dict[str, Any]], np.ndarray]


PRIMITIVE_KERNELS: dict[str, PrimitiveKernel] = {
    "plane": PrimitiveKernel(min_samples=3, fit_fn=fit_plane_from_points, dist_fn=plane_distances),
    "cylinder": PrimitiveKernel(min_samples=6, fit_fn=fit_cylinder, dist_fn=cylinder_distances),
    "sphere": PrimitiveKernel(min_samples=4, fit_fn=fit_sphere_algebraic, dist_fn=sphere_distances),
    "cone": PrimitiveKernel(min_samples=12, fit_fn=fit_cone, dist_fn=cone_distances),
    "torus": PrimitiveKernel(min_samples=20, fit_fn=fit_torus, dist_fn=torus_distances),
    "helix": PrimitiveKernel(min_samples=30, fit_fn=fit_helix, dist_fn=helix_distances),
}

