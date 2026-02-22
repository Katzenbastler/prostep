param(
    [string]$VenvPath = "C:\build\stl_recon_venv"
)

$ErrorActionPreference = "Stop"
$pythonExe = Join-Path $VenvPath "Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    throw "Virtual environment missing. Run ./scripts/setup_stl_reconstructor_windows.ps1 first."
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Push-Location $repoRoot
try {
    & $pythonExe -m stl_reconstructor gui
} finally {
    Pop-Location
}
