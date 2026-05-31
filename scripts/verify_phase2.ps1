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

Write-Host "Phase 2 verification passed (automated)." -ForegroundColor Green
Write-Host "Optional: PostgreSQL migration from backend dir: alembic upgrade head" -ForegroundColor DarkGray
Write-Host "Optional: Qdrant seed: python scripts/init_qdrant.py" -ForegroundColor DarkGray
Set-Location $RepoRoot
