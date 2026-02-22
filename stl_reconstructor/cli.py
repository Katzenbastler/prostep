from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import QualityMode, ReconstructionConfig
from .version import __version__


def _quality_mode(value: str) -> QualityMode:
    value = value.lower().strip()
    try:
        return QualityMode(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Invalid quality mode: {value}") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="stl-reconstructor",
        description="Feature-based STL to analytical STEP AP242 reconstruction",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Run headless reconstruction")
    run.add_argument("--input", required=True, help="Input STL file")
    run.add_argument("--output", required=False, help="Output STEP AP242 file")
    run.add_argument("--quality", type=_quality_mode, default=QualityMode.HIGH)
    run.add_argument("--tolerance-mm", type=float, default=0.01)
    run.add_argument("--disable-smoothing", action="store_true")
    run.add_argument("--seed", type=int, default=1337)

    sub.add_parser("gui", help="Start local GUI")

    upd_check = sub.add_parser("update-check", help="Check for available updates")
    upd_check.add_argument("--manifest", required=True, help="Manifest URL or local JSON path")
    upd_check.add_argument("--current-version", default=__version__)
    upd_check.add_argument("--channel", default="stable")

    upd_apply = sub.add_parser("update-apply", help="Download and stage update package")
    upd_apply.add_argument("--manifest", required=True, help="Manifest URL or local JSON path")
    upd_apply.add_argument("--install-dir", required=True, help="Install directory of the app")
    upd_apply.add_argument("--current-version", default=__version__)
    upd_apply.add_argument("--channel", default="stable")
    upd_apply.add_argument("--exe-name", default="STLReconstructor.exe")
    upd_apply.add_argument("--launch-apply", action="store_true", help="Launch update apply script immediately")
    return parser


def _run_headless(args: argparse.Namespace) -> int:
    from .pipeline import ReconstructionPipeline

    input_path = Path(args.input).resolve()
    output_path = Path(args.output).resolve() if args.output else None
    cfg = ReconstructionConfig(
        quality_mode=args.quality,
        enable_smoothing=not args.disable_smoothing,
        export_tolerance_mm=float(args.tolerance_mm),
        random_seed=int(args.seed),
    )

    def progress(p: float, msg: str) -> None:
        print(f"[{100.0 * p:6.2f}%] {msg}")

    pipeline = ReconstructionPipeline(config=cfg, progress=progress)
    result = pipeline.run(input_path, output_step=output_path)
    print(f"STEP: {result.output_step}")
    print(f"Elapsed: {result.elapsed_sec:.3f}s")
    print(f"Watertight: {result.brep.watertight}")
    print(f"Valid: {result.brep.valid}")
    print(f"Feature count: {len(result.features)}")
    return 0


def _run_update_check(args: argparse.Namespace) -> int:
    from .updater import check_for_update

    out = check_for_update(
        manifest_source=args.manifest,
        current_version=args.current_version,
        channel=args.channel,
    )
    print(json.dumps(out.__dict__, indent=2))
    return 0


def _run_update_apply(args: argparse.Namespace) -> int:
    from .updater import apply_update_from_manifest

    out = apply_update_from_manifest(
        manifest_source=args.manifest,
        current_version=args.current_version,
        install_dir=args.install_dir,
        channel=args.channel,
        executable_name=args.exe_name,
        launch_apply_script=bool(args.launch_apply),
    )
    print(json.dumps(out.__dict__, indent=2))
    return 0


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "gui":
        from .gui_app import run_gui

        run_gui()
        return 0
    if args.command == "run":
        return _run_headless(args)
    if args.command == "update-check":
        return _run_update_check(args)
    if args.command == "update-apply":
        return _run_update_apply(args)
    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
