from __future__ import annotations

import importlib
from dataclasses import dataclass


@dataclass(frozen=True)
class OccBackend:
    name: str
    root: str

    def module(self, submodule: str):
        return importlib.import_module(f"{self.root}.{submodule}")

    @staticmethod
    def call_static(obj, method: str, *args):
        fn = getattr(obj, method, None)
        if fn is None:
            fn = getattr(obj, f"{method}_s", None)
        if fn is None:
            raise AttributeError(f"Method {method} not available on {obj}")
        return fn(*args)


def _detect_backend() -> OccBackend:
    try:
        importlib.import_module("OCC.Core")
        return OccBackend(name="pythonocc", root="OCC.Core")
    except Exception:
        pass
    try:
        importlib.import_module("OCP")
        return OccBackend(name="ocp", root="OCP")
    except Exception as exc:
        raise RuntimeError(
            "No OpenCASCADE Python binding found. Install pythonocc-core or cadquery (OCP backend)."
        ) from exc


occ = _detect_backend()

