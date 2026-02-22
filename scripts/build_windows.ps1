param(
    [string]$BuildDir = 'C:\build\idle_hours',
    [string]$Configuration = 'Release'
)

$ErrorActionPreference = 'Stop'

$cmake = 'C:\Program Files\CMake\bin\cmake.exe'
$vcvars = 'C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat'

if (-not (Test-Path $cmake)) {
    throw 'CMake not found. Run ./scripts/setup_env_windows.ps1 first.'
}

if (-not (Test-Path $vcvars)) {
    throw 'MSVC Build Tools not found. Install Visual Studio Build Tools with C++ workload.'
}

$sourcePath = (Get-Item (Join-Path $PSScriptRoot '..')).FullName
$shortSourcePath = (cmd /c "for %I in (""$sourcePath"") do @echo %~sI").Trim()
if (-not $shortSourcePath) {
    $shortSourcePath = $sourcePath
}
New-Item -ItemType Directory -Force -Path $BuildDir | Out-Null

$batch = @"
@echo off
call "$vcvars"
"$cmake" -S "$shortSourcePath" -B "$BuildDir" -DCMAKE_BUILD_TYPE=$Configuration
if errorlevel 1 exit /b 1
"$cmake" --build "$BuildDir" --config $Configuration
"@

$tempBat = Join-Path $BuildDir 'build_local.bat'
Set-Content -Path $tempBat -Value $batch -Encoding ASCII

cmd /c $tempBat
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

Write-Host "Build complete: $BuildDir\\$Configuration\\idle_hours.exe"
