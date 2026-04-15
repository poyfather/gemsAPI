Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if (-not (Test-Path backend\.venv)) {
    throw "Virtual environment not found. Run .\scripts\setup.ps1 first."
}

& backend\.venv\Scripts\Activate.ps1
Write-Host "Running ruff..."
ruff check .
Write-Host "Running pytest..."
pytest -q
Write-Host "All checks passed."
