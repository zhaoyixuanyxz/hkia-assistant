# Phase 0 verification: backend pytest + frontend production build.
$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

Write-Host "==> backend: pytest" -ForegroundColor Cyan
Set-Location (Join-Path $RepoRoot "backend")
pytest -q

Write-Host "==> frontend: npm run build" -ForegroundColor Cyan
Set-Location (Join-Path $RepoRoot "frontend")
npm run build

Write-Host "Phase 0 verification passed." -ForegroundColor Green
Set-Location $RepoRoot
