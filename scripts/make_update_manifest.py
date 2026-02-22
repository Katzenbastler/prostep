from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate updater manifest JSON")
    parser.add_argument("--version", required=True, help="Version string, e.g. 0.2.0")
    parser.add_argument("--url", required=True, help="Download URL for release ZIP")
    parser.add_argument("--sha256", required=True, help="SHA256 checksum of ZIP")
    parser.add_argument("--channel", default="stable")
    parser.add_argument("--out", required=True, help="Output manifest path")
    args = parser.parse_args()

    manifest = {
        "app": "stl-reconstructor",
        "channels": {
            args.channel: {
                "version": args.version,
                "url": args.url,
                "sha256": args.sha256,
            }
        },
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Manifest written: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

