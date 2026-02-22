# Idle Hours - Chapter 1 Soft Violence (Engine Starter)

This scaffold gives you a custom-engine style foundation for a realistic horror game prototype:

- Blue void background
- White ground plane
- Player body with first-person camera
- Real AABB collision resolution against world geometry
- Fixed-step physics (120 Hz)
- Performance-oriented lighting shader (single directional + ambient, cheap per-vertex diffuse)

## Tech stack

- Language: C++20
- Build: CMake
- Runtime/render platform layer: raylib 5.5 (fetched automatically)

## One-time environment setup (Windows)

```powershell
./scripts/setup_env_windows.ps1
```

Optional Ninja install:

```powershell
./scripts/setup_env_windows.ps1 -WithNinja
```

## Build (Windows, robust path-safe)

```powershell
./scripts/build_windows.ps1
```

This builds to `C:\build\idle_hours` to avoid path-encoding issues with special characters in folder names.

## Run

```powershell
C:\build\idle_hours\Release\idle_hours.exe
```

## Controls

- `WASD`: move
- `SPACE`: jump
- `LEFT SHIFT`: sprint
- `ESC`: toggle cursor lock

## Why this lighting path is fast

- Single directional light only (no dynamic light loops)
- Diffuse term calculated in vertex shader
- Fragment shader does minimal work
- No dynamic shadows yet (add later only where needed)

## Next engine steps

1. Broadphase (grid or BVH) to scale collision objects.
2. Material system + baked lightmaps for static geometry.
3. GPU instancing for repeated props.
4. Async asset streaming and occlusion culling.

---

## STL -> Parametric STEP Reverse Engineering Tool (Python, local/offline)

This repo now also contains a fully local Python reverse-engineering tool:

- Input: `STL` triangle mesh
- Processing: feature-based primitive fitting + topological reconstruction
- Output: `STEP AP242` (`.step`) with analytical surfaces (plane/cylinder/sphere/cone/torus) and helix/thread handling in Ultra mode
- GUI: local dark-style desktop app with side-by-side before/after 3D viewer, progress bar, quality selection, and feature highlighting

### Quality modes

- `low`: aggressive downsampling, plane + cylinder only, fast
- `medium`: plane + cylinder + sphere, fillet-aware behavior
- `high`: adds cone + torus, tighter tolerances, topology refinement
- `ultra`: smallest tolerances, multistage RANSAC, helix/thread detection, extra analyses

### Install (Windows)

```powershell
./scripts/setup_stl_reconstructor_windows.ps1 -UpgradePip
```

### Run GUI (Dark mode window)

```powershell
./scripts/run_stl_reconstructor_gui.ps1
```

### Run Headless

```powershell
C:\build\stl_recon_venv\Scripts\python.exe -m stl_reconstructor run --input .\part.stl --quality ultra --tolerance-mm 0.01
```

### End-to-End validation (real STL + OCC + Open3D)

```powershell
C:\build\stl_recon_venv\Scripts\python.exe scripts/e2e_real_stl_occ_open3d.py --out-dir C:\build\stl_reconstructor_e2e --no-preview
```

Output summary:

- `C:\build\stl_reconstructor_e2e\e2e_summary.json`
- per-case STEP + JSON reports in the same folder

### Build a single-file `.exe`

```powershell
./scripts/build_stl_reconstructor_exe.ps1
```

Build output:

- `C:\build\stl_reconstructor_release\dist\STLReconstructor.exe`
- `C:\build\stl_reconstructor_release\release\STLReconstructor-<version>-win64.zip`
- `C:\build\stl_reconstructor_release\release\release_info.json`

### Updater workflow

Generate manifest for a release ZIP:

```powershell
C:\build\stl_recon_venv\Scripts\python.exe scripts/make_update_manifest.py --version 0.2.0 --url https://your-host/STLReconstructor-0.2.0-win64.zip --sha256 <sha256> --out .\packaging\update_manifest.json
```

Check for updates:

```powershell
C:\build\stl_recon_venv\Scripts\python.exe -m stl_reconstructor update-check --manifest .\packaging\update_manifest.json --current-version 0.2.0
```

Download and stage update:

```powershell
C:\build\stl_recon_venv\Scripts\python.exe -m stl_reconstructor update-apply --manifest .\packaging\update_manifest.json --install-dir C:\Path\To\App --current-version 0.2.0 --exe-name STLReconstructor.exe
```

### Key module entrypoints

- `stl_reconstructor/preprocess.py`: mesh repair + normals + feature-aware smoothing + voxel downsampling
- `stl_reconstructor/segmentation.py`: multi-primitive RANSAC segmentation
- `stl_reconstructor/brep_builder.py`: analytical OCC face creation + sewing/healing + solid creation
- `stl_reconstructor/step_export.py`: STEP AP242 export with configurable unit/tolerance
- `stl_reconstructor/gui_app.py`: local dual-viewer desktop GUI
- `stl_reconstructor/updater.py`: manifest-based update check/download/staging
