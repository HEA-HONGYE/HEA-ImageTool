param(
    [switch]$Silent
)

$ErrorActionPreference = "SilentlyContinue"

function Remove-Tree {
    param([string]$Path)
    if ([string]::IsNullOrWhiteSpace($Path)) {
        return
    }
    if (Test-Path -LiteralPath $Path) {
        Remove-Item -LiteralPath $Path -Recurse -Force
    }
}

function Remove-RegTree {
    param([string]$Path)
    if (Test-Path -LiteralPath $Path) {
        Remove-Item -LiteralPath $Path -Recurse -Force
    }
}

$appName = "HEA"
$candidateDirs = @(
    Join-Path $env:LOCALAPPDATA $appName,
    Join-Path $env:APPDATA $appName,
    Join-Path $env:TEMP $appName,
    Join-Path $env:TEMP "HEA",
    Join-Path $env:TEMP "hea"
)

foreach ($dir in $candidateDirs | Select-Object -Unique) {
    Remove-Tree $dir
}

Remove-RegTree "HKCU:\Software\HEA"

if (-not $Silent) {
    Add-Type -AssemblyName PresentationFramework
    [System.Windows.MessageBox]::Show("HEA 用户配置、缓存和注册表项已清理。", "HEA 一键清理", "OK", "Information") | Out-Null
}
