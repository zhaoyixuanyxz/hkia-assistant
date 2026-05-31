# 预拉取 Compose 所需镜像（Docker Hub 官方，带简单重试）
param(
    [string]$EnvFile = (Join-Path (Split-Path $PSScriptRoot -Parent) "docker.intl.env"),
    [int]$MaxRetries = 3
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $EnvFile)) {
    Write-Host "[pull] docker.intl.env not found: $EnvFile" -ForegroundColor Yellow
    exit 1
}

$vars = @{}
Get-Content $EnvFile | ForEach-Object {
    $line = $_.Trim()
    if ($line -eq "" -or $line.StartsWith("#")) { return }
    $idx = $line.IndexOf("=")
    if ($idx -lt 1) { return }
    $vars[$line.Substring(0, $idx).Trim()] = $line.Substring($idx + 1).Trim()
}

$images = @(
    $vars["POSTGRES_IMAGE"],
    $vars["QDRANT_IMAGE"],
    $vars["PYTHON_IMAGE"],
    $vars["NODE_IMAGE"]
) | Where-Object { $_ }

if ($images.Count -eq 0) {
    Write-Host "[pull] No images defined in $EnvFile" -ForegroundColor Yellow
    exit 1
}

function Pull-ImageWithRetry {
    param([string]$Image, [int]$Retries)
    for ($i = 1; $i -le $Retries; $i++) {
        Write-Host "[pull] ($i/$Retries) $Image"
        docker pull $Image
        if ($LASTEXITCODE -eq 0) { return $true }
        if ($i -lt $Retries) {
            Write-Host "[pull] retry in 5s..." -ForegroundColor Yellow
            Start-Sleep -Seconds 5
        }
    }
    return $false
}

$failed = @()
foreach ($img in $images) {
    if (-not (Pull-ImageWithRetry -Image $img -Retries $MaxRetries)) {
        $failed += $img
    }
}

if ($failed.Count -gt 0) {
    Write-Host "[pull] Failed:" -ForegroundColor Red
    $failed | ForEach-Object { Write-Host "  - $_" -ForegroundColor Red }
    Write-Host "[pull] Check VPN/proxy or Docker Desktop network settings." -ForegroundColor Yellow
    exit 1
}

Write-Host "[pull] All base images ready." -ForegroundColor Green
exit 0
