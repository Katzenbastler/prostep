from __future__ import annotations

import numpy as np

from .occ_runtime import occ

BRep = occ.module("BRep")
BRepMesh = occ.module("BRepMesh")
TopAbs = occ.module("TopAbs")
TopExp = occ.module("TopExp")
TopLoc = occ.module("TopLoc")
TopoDS_module = occ.module("TopoDS")

BRep_Tool = BRep.BRep_Tool
BRepMesh_IncrementalMesh = BRepMesh.BRepMesh_IncrementalMesh
TopAbs_FACE = TopAbs.TopAbs_FACE
TopAbs_REVERSED = TopAbs.TopAbs_REVERSED
TopExp_Explorer = TopExp.TopExp_Explorer
TopLoc_Location = TopLoc.TopLoc_Location

if occ.name == "pythonocc":
    _topods = TopoDS_module.topods

    def _to_face(shape):
        return _topods.Face(shape)

else:
    _topods_cls = getattr(TopoDS_module, "TopoDS", TopoDS_module)

    def _to_face(shape):
        return _topods_cls.Face_s(shape)


def tessellate_shape(shape, linear_deflection: float = 0.2, angular_deflection: float = 0.3) -> tuple[np.ndarray, np.ndarray]:
    BRepMesh_IncrementalMesh(shape, float(linear_deflection), False, float(angular_deflection), True)
    vertices: list[list[float]] = []
    faces: list[list[int]] = []

    explorer = TopExp_Explorer(shape, TopAbs_FACE)
    while explorer.More():
        face = _to_face(explorer.Current())
        location = TopLoc_Location()
        triangulation = occ.call_static(BRep_Tool, "Triangulation", face, location)
        if triangulation is None:
            explorer.Next()
            continue

        transform = location.Transformation()
        offset = len(vertices)
        if hasattr(triangulation, "Nodes"):
            nodes = triangulation.Nodes()

            def node_get(idx: int):
                return nodes.Value(idx)

        else:

            def node_get(idx: int):
                return triangulation.Node(idx)

        if hasattr(triangulation, "Triangles"):
            triangles = triangulation.Triangles()
            if hasattr(triangles, "Value"):

                def tri_get(idx: int):
                    return triangles.Value(idx)

            else:

                def tri_get(idx: int):
                    return triangulation.Triangle(idx)

        else:

            def tri_get(idx: int):
                return triangulation.Triangle(idx)

        for i in range(1, triangulation.NbNodes() + 1):
            p = node_get(i).Transformed(transform)
            vertices.append([float(p.X()), float(p.Y()), float(p.Z())])

        for i in range(1, triangulation.NbTriangles() + 1):
            t = tri_get(i)
            n1, n2, n3 = t.Get()
            i1 = offset + int(n1) - 1
            i2 = offset + int(n2) - 1
            i3 = offset + int(n3) - 1
            if face.Orientation() == TopAbs_REVERSED:
                faces.append([i1, i3, i2])
            else:
                faces.append([i1, i2, i3])
        explorer.Next()

    if not vertices or not faces:
        return np.empty((0, 3), dtype=np.float64), np.empty((0, 3), dtype=np.int32)
    return np.asarray(vertices, dtype=np.float64), np.asarray(faces, dtype=np.int32)
