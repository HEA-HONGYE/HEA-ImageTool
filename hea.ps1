$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    Write-Host "Missing virtual environment: .venv" -ForegroundColor Red
    Write-Host "Please run: py -m venv .venv"
    Write-Host "Then run: .venv\Scripts\python -m pip install -r requirements.txt"
    exit 1
}

& $python -m image_toolbox.launcher
