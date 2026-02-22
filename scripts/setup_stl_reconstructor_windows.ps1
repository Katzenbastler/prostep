param(
    [string]$VenvPath = "C:\build\stl_recon_venv",
    [switch]$UpgradePip
)

$ErrorActionPreference = "Stop"

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python not found in PATH."
}

if (-not (Test-Path $VenvPath)) {
    python -m venv $VenvPath
}

$pythonExe = Join-Path $VenvPath "Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    throw "Virtual environment Python not found: $pythonExe"
}

if ($UpgradePip) {
    & $pythonExe -m pip install --upgrade pip setuptools wheel
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$requirementsPath = Join-Path $repoRoot "requirements-stl-reconstructor.txt"
if (-not (Test-Path $requirementsPath)) {
    throw "Requirements file not found: $requirementsPath"
}

Push-Location $repoRoot
try {
    & $pythonExe -m pip install -r $requirementsPath
    & $pythonExe -m pip install -e $repoRoot
} finally {
    Pop-Location
}

Write-Host ""
Write-Host "Setup complete."
Write-Host "Headless run:"
Write-Host "  $pythonExe -m stl_reconstructor run --input .\path\to\mesh.stl --quality high"
Write-Host "GUI:"
Write-Host "  $pythonExe -m stl_reconstructor gui"
