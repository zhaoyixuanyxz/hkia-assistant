$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot

Write-Host "==> backend: pytest" -ForegroundColor Cyan
Set-Location (Join-Path $RepoRoot "backend")
pytest -q

Write-Host "==> frontend: npm run build" -ForegroundColor Cyan
Set-Location (Join-Path $RepoRoot "frontend")
npm run build

Write-Host "==> frontend: Playwright smoke" -ForegroundColor Cyan
npm run test:e2e

Write-Host "Phase 1 verification passed (automated)." -ForegroundColor Green
Set-Location $RepoRoot
