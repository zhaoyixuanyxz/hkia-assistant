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

Set-Location $RepoRoot
if (Get-Command docker -ErrorAction SilentlyContinue) {
  Write-Host "==> docker compose config" -ForegroundColor Cyan
  docker compose config | Out-Null
} else {
  Write-Host "docker not found, skipped compose validation." -ForegroundColor DarkGray
}

Write-Host "Phase 3 verification passed (automated)." -ForegroundColor Green
