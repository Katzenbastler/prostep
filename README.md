# proSTEP — STL to STEP AP242 Reconstructor

Feature-based reverse engineering tool. Segments an STL mesh into geometric primitives (planes, cylinders, cones, spheres, tori) and exports a parametric STEP AP242 B-rep.

Version: 3.0.0b0

## Requirements

- Python 3.11 (open3d does not yet ship wheels for 3.12+)
- Linux or Windows

## Setup

```bash
bash setup.sh
source v/bin/activate
```

## Usage

**Headless:**
```bash
stl-reconstructor run --input model.stl --output model.step --quality high
```

Quality modes: `draft`, `standard`, `high`, `ultra`

**GUI:**
```bash
stl-reconstructor gui
```

**Via script directly:**
```bash
python scripts/proSTEP.py run --input model.stl
```

## Options

| Flag | Default | Description |
|------|---------|-------------|
| `--quality` | `high` | Reconstruction quality |
| `--tolerance-mm` | `0.01` | Export tolerance |
| `--disable-smoothing` | off | Skip mesh smoothing |
| `--seed` | `1337` | RANSAC random seed |
