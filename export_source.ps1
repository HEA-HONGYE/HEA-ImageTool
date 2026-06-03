$ErrorActionPreference = "Stop"

$root = $PSScriptRoot
$exportRoot = Join-Path $root "release"
$target = Join-Path $exportRoot "hea-v1-source"

if (Test-Path -LiteralPath $target) {
    Remove-Item -LiteralPath $target -Recurse -Force
}

New-Item -ItemType Directory -Force -Path $target | Out-Null

$excludeDirs = @(".git", ".venv", "__pycache__", "output", "release", ".pytest_cache", ".mypy_cache")
$excludeFiles = @("*.pyc", "*.pyo")

Get-ChildItem -LiteralPath $root -Force | ForEach-Object {
    if ($excludeDirs -contains $_.Name) {
        return
    }

    $destination = Join-Path $target $_.Name
    if ($_.PSIsContainer) {
        Copy-Item -LiteralPath $_.FullName -Destination $destination -Recurse -Force -Exclude $excludeFiles
    } else {
        Copy-Item -LiteralPath $_.FullName -Destination $destination -Force
    }
}

Write-Host "Exported to: $target"
