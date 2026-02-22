param(
    [switch]$WithNinja
)

$ErrorActionPreference = 'Stop'

if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
    Write-Error "winget is not available. Install App Installer from Microsoft Store first."
}

Write-Host "Installing required build tools..."

winget install --id Kitware.CMake --accept-package-agreements --accept-source-agreements --silent
winget install --id Git.Git --accept-package-agreements --accept-source-agreements --silent

if ($WithNinja) {
    winget install --id Ninja-build.Ninja --accept-package-agreements --accept-source-agreements --silent
}

Write-Host "Done. Restart your terminal, then run:"
Write-Host "  cmake -S . -B build -DCMAKE_BUILD_TYPE=Release"
Write-Host "  cmake --build build --config Release"
