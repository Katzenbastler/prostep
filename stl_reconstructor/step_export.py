from __future__ import annotations

from pathlib import Path

from .models import BRepBuildInfo
from .occ_runtime import occ

IFSelect = occ.module("IFSelect")
Interface = occ.module("Interface")
STEPControl = occ.module("STEPControl")
BRep = occ.module("BRep")
TopoDS_module = occ.module("TopoDS")

IFSelect_RetDone = IFSelect.IFSelect_RetDone
Interface_Static = Interface.Interface_Static
STEPControl_AsIs = STEPControl.STEPControl_AsIs
STEPControl_Writer = STEPControl.STEPControl_Writer
BRep_Builder = BRep.BRep_Builder
TopoDS_Compound = TopoDS_module.TopoDS_Compound


def choose_export_shape(brep: BRepBuildInfo):
    if brep.solid is not None:
        return brep.solid
    if brep.shell is not None:
        return brep.shell
    if brep.faces:
        builder = BRep_Builder()
        comp = TopoDS_Compound()
        builder.MakeCompound(comp)
        for face in brep.faces:
            builder.Add(comp, face)
        return comp
    return None


def export_step_ap242(
    brep: BRepBuildInfo,
    out_path: str | Path,
    unit: str = "MM",
    tolerance_mm: float = 0.01,
) -> Path:
    target = Path(out_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    shape = choose_export_shape(brep)
    if shape is None:
        raise RuntimeError("No shape available for STEP export.")

    occ.call_static(Interface_Static, "SetCVal", "write.step.schema", "AP242DIS")
    occ.call_static(Interface_Static, "SetCVal", "xstep.cascade.unit", str(unit).upper())
    occ.call_static(Interface_Static, "SetRVal", "write.precision.val", float(max(1e-6, tolerance_mm)))

    writer = STEPControl_Writer()
    writer.Transfer(shape, STEPControl_AsIs)
    status = writer.Write(str(target))
    if status != IFSelect_RetDone:
        raise RuntimeError(f"STEP export failed with status {status}")
    return target
