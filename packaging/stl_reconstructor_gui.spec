# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules


project_root = Path.cwd()
block_cipher = None

datas = []
binaries = []
hiddenimports = []

for pkg in ["trimesh", "OCP", "scipy", "numpy"]:
    datas += collect_data_files(
        pkg,
        excludes=[
            "**/tests/**",
            "**/test/**",
            "**/testing/**",
            "**/examples/**",
            "**/benchmarks/**",
            "**/docs/**",
            "**/__pycache__/**",
        ],
    )
    binaries += collect_dynamic_libs(pkg)

datas += [
    (str(project_root / "assets" / "icons" / "proSTEP.ico"), "assets/icons"),
    (str(project_root / "assets" / "icons" / "prostep_brand.png"), "assets/icons"),
]

hiddenimports += collect_submodules("stl_reconstructor")
hiddenimports += [
    "OCP",
    "OCP.BRep",
    "OCP.BRepBuilderAPI",
    "OCP.BRepCheck",
    "OCP.BRepMesh",
    "OCP.BRepOffsetAPI",
    "OCP.Geom",
    "OCP.GeomAPI",
    "OCP.GeomAbs",
    "OCP.IFSelect",
    "OCP.Interface",
    "OCP.ShapeFix",
    "OCP.STEPControl",
    "OCP.TColgp",
    "OCP.TopAbs",
    "OCP.TopExp",
    "OCP.TopLoc",
    "OCP.TopoDS",
    "OCP.gp",
]

a = Analysis(
    [str(project_root / "stl_reconstructor" / "app_entry_gui.py")],
    pathex=[str(project_root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "open3d.examples",
        "open3d.ml",
        "matplotlib",
        "IPython",
        "pytest",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="prostep",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(project_root / "assets" / "icons" / "proSTEP.ico"),
    version=str(project_root / "packaging" / "windows_version_info.txt"),
)
