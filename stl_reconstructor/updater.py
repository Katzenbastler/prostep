from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from zipfile import ZipFile

import requests
from packaging.version import Version


@dataclass
class UpdateCandidate:
    version: str
    url: str
    sha256: str | None
    channel: str


@dataclass
class UpdateResult:
    checked: bool
    update_available: bool
    current_version: str
    latest_version: str | None
    downloaded_file: str | None = None
    staging_dir: str | None = None
    apply_script: str | None = None
    message: str = ""


def _to_version(v: str) -> Version:
    return Version(str(v).strip())


def _read_manifest(source: str) -> dict[str, Any]:
    if source.startswith("http://") or source.startswith("https://"):
        response = requests.get(source, timeout=30)
        response.raise_for_status()
        return response.json()
    return json.loads(Path(source).read_text(encoding="utf-8"))


def _extract_candidate(manifest: dict[str, Any], channel: str) -> UpdateCandidate | None:
    channels = manifest.get("channels")
    if isinstance(channels, dict) and channel in channels:
        item = channels[channel]
        if all(k in item for k in ("version", "url")):
            return UpdateCandidate(
                version=str(item["version"]),
                url=str(item["url"]),
                sha256=str(item["sha256"]) if item.get("sha256") else None,
                channel=channel,
            )
    if all(k in manifest for k in ("version", "url")):
        return UpdateCandidate(
            version=str(manifest["version"]),
            url=str(manifest["url"]),
            sha256=str(manifest["sha256"]) if manifest.get("sha256") else None,
            channel=channel,
        )
    return None


def check_for_update(manifest_source: str, current_version: str, channel: str = "stable") -> UpdateResult:
    manifest = _read_manifest(manifest_source)
    candidate = _extract_candidate(manifest, channel=channel)
    if candidate is None:
        return UpdateResult(
            checked=True,
            update_available=False,
            current_version=current_version,
            latest_version=None,
            message="No valid update candidate in manifest.",
        )

    cur = _to_version(current_version)
    latest = _to_version(candidate.version)
    if latest > cur:
        return UpdateResult(
            checked=True,
            update_available=True,
            current_version=current_version,
            latest_version=candidate.version,
            message=f"Update available: {current_version} -> {candidate.version}",
        )
    return UpdateResult(
        checked=True,
        update_available=False,
        current_version=current_version,
        latest_version=candidate.version,
        message="Already up to date.",
    )


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _download_file(url: str, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        with out_path.open("wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)


def _build_apply_script(staging_dir: Path, install_dir: Path, executable_name: str) -> Path:
    script = install_dir / "_apply_update.cmd"
    content = f"""@echo off
setlocal
timeout /t 2 /nobreak >nul
robocopy "{staging_dir}" "{install_dir}" /E /NFL /NDL /NJH /NJS /NP /R:2 /W:1
if %errorlevel% GEQ 8 exit /b 1
start "" "{install_dir / executable_name}"
exit /b 0
"""
    script.write_text(content, encoding="ascii")
    return script


def apply_update_from_manifest(
    manifest_source: str,
    current_version: str,
    install_dir: str | Path,
    channel: str = "stable",
    executable_name: str = "STLReconstructor.exe",
    launch_apply_script: bool = False,
) -> UpdateResult:
    manifest = _read_manifest(manifest_source)
    candidate = _extract_candidate(manifest, channel=channel)
    if candidate is None:
        return UpdateResult(
            checked=True,
            update_available=False,
            current_version=current_version,
            latest_version=None,
            message="No valid update candidate in manifest.",
        )
    if _to_version(candidate.version) <= _to_version(current_version):
        return UpdateResult(
            checked=True,
            update_available=False,
            current_version=current_version,
            latest_version=candidate.version,
            message="Already up to date.",
        )

    install_path = Path(install_dir).resolve()
    cache_dir = install_path / "_updates"
    cache_dir.mkdir(parents=True, exist_ok=True)
    downloaded = cache_dir / f"update_{candidate.version}.zip"
    _download_file(candidate.url, downloaded)
    if candidate.sha256:
        sha = _sha256_file(downloaded)
        if sha.lower() != candidate.sha256.lower():
            raise RuntimeError(f"SHA256 mismatch for update package. expected={candidate.sha256} actual={sha}")

    staging = install_path / "_update_staging" / f"{candidate.version}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    staging.mkdir(parents=True, exist_ok=True)
    with ZipFile(downloaded, "r") as zf:
        zf.extractall(staging)

    script_path = None
    if os.name == "nt":
        script_path = _build_apply_script(staging, install_path, executable_name)
        if launch_apply_script:
            subprocess.Popen(
                ["cmd", "/c", "start", "", str(script_path)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

    return UpdateResult(
        checked=True,
        update_available=True,
        current_version=current_version,
        latest_version=candidate.version,
        downloaded_file=str(downloaded),
        staging_dir=str(staging),
        apply_script=str(script_path) if script_path else None,
        message=f"Update {candidate.version} downloaded and staged.",
    )

