from __future__ import annotations

import math

import numpy as np

from stl_reconstructor.fitting import fit_cylinder, fit_plane_from_points, fit_sphere_algebraic


def test_plane_fit_smoke() -> None:
    rng = np.random.default_rng(2)
    xy = rng.normal(size=(500, 2))
    z = np.full((500, 1), 3.5)
    pts = np.hstack([xy, z])
    model = fit_plane_from_points(pts)
    assert model is not None
    normal = model["normal"]
    assert abs(abs(normal[2]) - 1.0) < 1e-4


def test_sphere_fit_smoke() -> None:
    rng = np.random.default_rng(3)
    center = np.array([2.0, -1.0, 4.0])
    radius = 5.0
    phi = rng.uniform(0.0, 2.0 * math.pi, 1400)
    cost = rng.uniform(-1.0, 1.0, 1400)
    sint = np.sqrt(1.0 - cost**2)
    pts = np.column_stack(
        [
            center[0] + radius * sint * np.cos(phi),
            center[1] + radius * sint * np.sin(phi),
            center[2] + radius * cost,
        ]
    )
    model = fit_sphere_algebraic(pts)
    assert model is not None
    assert np.linalg.norm(model["center"] - center) < 1e-2
    assert abs(model["radius"] - radius) < 1e-2


def test_cylinder_fit_smoke() -> None:
    rng = np.random.default_rng(4)
    radius = 3.25
    z = rng.uniform(-8.0, 8.0, 2000)
    t = rng.uniform(0.0, 2.0 * math.pi, 2000)
    x = radius * np.cos(t)
    y = radius * np.sin(t)
    pts = np.column_stack([x, y, z])
    model = fit_cylinder(pts)
    assert model is not None
    assert abs(model["radius"] - radius) < 0.05

