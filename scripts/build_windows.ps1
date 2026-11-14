# Build the Windows package: dist\OptimaTime\ (two programs) and OptimaTime-<version>-win64.zip
#
# Prerequisites on the build PC: uv (winget install astral-sh.uv), Node.js LTS (winget install OpenJS.NodeJS.LTS).
# Run from the repository root in PowerShell:
#   powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

Write-Host "== Python dependencies (with the build group)"
uv sync --group build

Write-Host "== Models (pinned revisions, SHA-256 checked)"
uv run python scripts/fetch_models.py

Write-Host "== UI"
Push-Location frontend
npm ci
npm run build
Pop-Location

Write-Host "== Tests"
uv run pytest -q
if ($LASTEXITCODE -ne 0) { throw "tests failed" }

Write-Host "== PyInstaller"
uv run pyinstaller packaging/optima-time.spec --noconfirm --distpath dist --workpath build\work
if ($LASTEXITCODE -ne 0) { throw "pyinstaller failed" }

Write-Host "== Self-test of the package"
& dist\OptimaTime\optima-time.exe --self-test
if ($LASTEXITCODE -ne 0) { throw "self-test of the package failed" }

$version = (uv run python -c "import optima_time; print(optima_time.__version__)").Trim()
$zip = "dist\OptimaTime-$version-win64.zip"
if (Test-Path $zip) { Remove-Item $zip }
Compress-Archive -Path dist\OptimaTime -DestinationPath $zip
Write-Host "== Done: $zip"
