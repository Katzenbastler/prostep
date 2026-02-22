param(
    [string]$VenvPath = "C:\build\stl_recon_venv",
    [string]$OutputRoot = "C:\build\stl_reconstructor_release",
    [switch]$Clean
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$pyExe = Join-Path $VenvPath "Scripts\python.exe"
if (-not (Test-Path $pyExe)) {
    throw "Python in venv not found: $pyExe"
}

$specPath = Join-Path $repoRoot "packaging\stl_reconstructor_gui.spec"
if (-not (Test-Path $specPath)) {
    throw "PyInstaller spec not found: $specPath"
}

if ($Clean -and (Test-Path $OutputRoot)) {
    Remove-Item -Recurse -Force $OutputRoot
}

$buildPath = Join-Path $OutputRoot "build"
$distPath = Join-Path $OutputRoot "dist"
$releasePath = Join-Path $OutputRoot "release"
New-Item -ItemType Directory -Force -Path $buildPath, $distPath, $releasePath | Out-Null

$version = (& $pyExe -c "from stl_reconstructor.version import __version__; print(__version__)").Trim()
if (-not $version) {
    throw "Could not read app version."
}

Push-Location $repoRoot
try {
    & $pyExe -m PyInstaller --noconfirm --clean --workpath $buildPath --distpath $distPath $specPath
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller build failed."
    }
} finally {
    Pop-Location
}

$exePath = Join-Path $distPath "prostep.exe"
if (-not (Test-Path $exePath)) {
    throw "Built exe not found: $exePath"
}

$versionDir = Join-Path $releasePath "prostep-$version-win64"
New-Item -ItemType Directory -Force -Path $versionDir | Out-Null
Copy-Item $exePath (Join-Path $versionDir "prostep.exe") -Force

$zipPath = Join-Path $releasePath "prostep-$version-win64.zip"
if (Test-Path $zipPath) { Remove-Item -Force $zipPath }
Compress-Archive -Path (Join-Path $versionDir "*") -DestinationPath $zipPath

$sha = (Get-FileHash -Path $zipPath -Algorithm SHA256).Hash.ToLower()
$releaseInfo = @{
    version = $version
    exe = (Join-Path $versionDir "prostep.exe")
    zip = $zipPath
    sha256 = $sha
    created_utc = (Get-Date).ToUniversalTime().ToString("o")
}
$releaseInfoPath = Join-Path $releasePath "release_info.json"
$releaseInfo | ConvertTo-Json -Depth 8 | Set-Content -Path $releaseInfoPath -Encoding UTF8

Write-Host ""
Write-Host "Build complete."
Write-Host "EXE: $exePath"
Write-Host "ZIP: $zipPath"
Write-Host "SHA256: $sha"
Write-Host "release_info: $releaseInfoPath"
