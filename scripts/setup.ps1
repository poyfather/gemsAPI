Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

Write-Host "Setting up Lapidary backend..."

if (-not (Test-Path backend\.venv)) {
    python -m venv backend\.venv
}

& backend\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r backend\requirements.txt
pip install -r requirements.txt

Write-Host "Setup complete. Run .\scripts\test.ps1 to verify."
